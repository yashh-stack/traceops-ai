"""
Offline Baseline Builder for TraceOps AI.
Synthesizes golden agent trajectories using Gemini Pro and refreshes
the PostgreSQL + pgvector centroid store and local in-process centroid cache.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
import numpy as np

from traceops.config import get_settings
from traceops.guards.semantic_drift import SemanticDriftScorer

logger = logging.getLogger("traceops.baseline_builder")

class BaselineBuilder:
    """
    Offline Trajectory Baseline Builder using Gemini Flash via google-genai SDK.
    Generates golden step sequences for SRE goals and updates vector centroids.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        pg_url: Optional[str] = None
    ):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gemini_api_key.get_secret_value()
        self.model_name = model_name or settings.gemini_baseline_model
        self.pg_url = pg_url if pg_url is not None else settings.database_url.get_secret_value()
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Pro client: {e}")

    def synthesize_golden_trajectory(
        self,
        scenario: str,
        goal: str
    ) -> List[Dict[str, Any]]:
        """
        Synthesize golden step sequences for an SRE goal.
        Falls back to curated golden trajectories if API key is not present.
        """
        if self.client:
            try:
                prompt = f"""
You are a Principal Google Cloud SRE. Synthesize the golden (ideal) trajectory of agent tool actions
to solve the following problem with zero wasted actions:
Scenario: {scenario}
Goal: {goal}

Output JSON as a list of tool objects, e.g.:
[
  {{"step": 1, "tool_name": "query_gke_telemetry", "intent": "inspect cluster status"}},
  {{"step": 2, "tool_name": "fetch_pod_logs", "intent": "pull 500 error logs"}},
  {{"step": 3, "tool_name": "get_service_metrics", "intent": "verify latency spikes"}}
]
"""
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                raw_text = response.text or "[]"
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                steps = json.loads(raw_text)
                return steps
            except Exception as e:
                logger.warning(f"Gemini Pro synthesis failed ({e}), using curated golden trajectory.")

        # Curated golden trajectory fallback
        return [
            {"step": 1, "tool_name": "query_gke_telemetry", "intent": "check cluster health"},
            {"step": 2, "tool_name": "fetch_pod_logs", "intent": "extract stack trace and status codes"},
            {"step": 3, "tool_name": "get_service_metrics", "intent": "correlate cpu and memory spikes"},
            {
                "step": 4,
                "tool_name": "run_canary_test",
                "intent": "validate candidate fix in isolated namespace",
            },
        ]

    def refresh_centroids(
        self,
        scorer: SemanticDriftScorer,
        scenario: str,
        trajectory_steps: List[Dict[str, Any]]
    ) -> List[float]:
        """
        Compute golden centroid vector from trajectory steps and update the scorer cache.
        Optionally persists to PostgreSQL + pgvector if DATABASE_URL is configured.
        """
        vectors = []
        for step in trajectory_steps:
            text = f"{step.get('tool_name', '')} {step.get('intent', '')}"
            vec = scorer.embed_step_in_process(text)
            vectors.append(vec)

        if not vectors:
            return [0.0] * scorer.dimension

        centroid = np.mean(vectors, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        centroid_list = [float(x) for x in centroid]
        scorer.set_golden_centroid(scenario, centroid_list)

        # Store in PostgreSQL + pgvector if connection URL is available
        if self.pg_url and "postgres" in self.pg_url:
            self._save_to_pgvector(scenario, centroid_list)

        return centroid_list

    def _save_to_pgvector(self, scenario: str, vector: List[float]) -> None:
        """Save centroid to pgvector table if live database is accessible."""
        try:
            import psycopg  # pyright: ignore[reportMissingImports]
            with psycopg.connect(self.pg_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS golden_centroids (
                            scenario VARCHAR(64) PRIMARY KEY,
                            centroid vector(64),
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("""
                        INSERT INTO golden_centroids (scenario, centroid)
                        VALUES (%s, %s)
                        ON CONFLICT (scenario) DO UPDATE SET centroid = EXCLUDED.centroid;
                    """, (scenario, vector))
                    conn.commit()
            logger.info(f"Persisted golden centroid for '{scenario}' into PostgreSQL + pgvector.")
        except Exception as e:
            logger.info(f"pgvector write skipped ({e}); using local memory cache.")
