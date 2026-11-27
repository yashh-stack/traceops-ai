"""
TraceOps AI Circuit Breaker Core Engine.
Coordinates Tier-1 Deterministic Guard, Tier-2 Semantic Drift Scorer,
Tier-3 LangGraph State Machine, PII scrubbing, and async OTel emission.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Literal, Optional, Set, Type

from pydantic import BaseModel

from traceops.config import get_settings
from traceops.guards.deterministic import DeterministicGuard, Tier1Violation
from traceops.guards.semantic_drift import SemanticDriftScorer
from traceops.otel_exporter import TraceOpsOtelEmitter
from traceops.security import redact_payload, redact_string
from traceops.state_machine import CircuitState, deterministic_circuit_graph

logger = logging.getLogger("traceops.circuit_breaker")


class CircuitBreakerError(Exception):
    """Raised when execution is halted by TraceOps in 'enforce' mode."""

    def __init__(self, message: str, decision_record: Dict[str, Any]):
        super().__init__(message)
        self.message = message
        self.decision_record = decision_record


class CircuitBreaker:
    """
    Main Circuit Breaker Engine for TraceOps AI.
    Combines microsecond deterministic checks with LangGraph policy arbitration.
    """

    def __init__(
        self,
        mode: Literal["shadow", "enforce"] = "enforce",
        max_identical_calls: int = 3,
        max_cost_usd: float = 0.50,
        max_tokens: int = 25000,
        drift_threshold: float = 0.55,
        warn_threshold: float = 0.40,
        allowed_tools: Optional[Set[str]] = None,
        tool_schemas: Optional[Dict[str, Type[BaseModel]]] = None,
        fail_open_tier3: Optional[bool] = None,
        otel_emitter: Optional[TraceOpsOtelEmitter] = None,
    ):
        settings = get_settings()
        self.mode: Literal["shadow", "enforce"] = mode
        self.fail_open_tier3: bool = (
            fail_open_tier3 if fail_open_tier3 is not None else settings.fail_open_tier3
        )
        self.deterministic_guard = DeterministicGuard(
            max_identical_calls=max_identical_calls,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
            allowed_tools=allowed_tools,
            tool_schemas=tool_schemas,
        )
        self.drift_scorer = SemanticDriftScorer(
            drift_threshold=drift_threshold,
            warn_threshold=warn_threshold,
        )
        self.otel_emitter = otel_emitter or TraceOpsOtelEmitter.get_instance()
        self.total_simulated_usd_saved: float = 0.0

    def set_mode(self, mode: Literal["shadow", "enforce"]) -> None:
        """Dynamically toggle between shadow and enforce modes."""
        self.mode = mode

    def reset_trace(self) -> None:
        """Reset state for a new agent execution trace."""
        self.deterministic_guard.reset()

    def evaluate_step(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        step_cost_usd: float = 0.0,
        step_tokens: int = 0,
        step_context: str = "",
        scenario: str = "default",
        trace_id: Optional[str] = None,
        mode_override: Optional[Literal["shadow", "enforce"]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single agent tool-call step on the synchronous hot path.
        Guarantees <15 ms latency target with 0 LLM calls and race-free mode overrides.
        """
        start_ns = time.perf_counter_ns()
        current_trace_id = trace_id or str(uuid.uuid4())
        effective_mode: Literal["shadow", "enforce"] = mode_override or self.mode

        # Step 1: Tier-1 Deterministic Guard (<1 ms)
        tier1_status: Literal["PASS", "FAIL"] = "PASS"
        tier1_rule: Optional[str] = None
        tier1_message: Optional[str] = None
        tier1_details: Dict[str, Any] = {}

        try:
            self.deterministic_guard.evaluate_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                step_cost_usd=step_cost_usd,
                step_tokens=step_tokens,
            )
        except Tier1Violation as v:
            tier1_status = "FAIL"
            tier1_rule = v.rule
            tier1_message = v.message
            tier1_details = v.details

        # Step 2: Tier-2 Semantic Drift Scorer (<5 ms)
        eval_text = f"{tool_name} {arguments} {step_context}".strip()
        drift_res = self.drift_scorer.evaluate_drift(eval_text, scenario=scenario)

        tier2_status = drift_res["status"]
        drift_score = drift_res["drift_score"]
        drift_message = drift_res["message"]

        # Step 3: Tier-3 Deterministic LangGraph State Machine (<2 ms)
        initial_state: CircuitState = {
            "tool_name": tool_name,
            "arguments": arguments,
            "step_cost_usd": step_cost_usd,
            "step_tokens": step_tokens,
            "step_context": step_context,
            "scenario": scenario,
            "mode": effective_mode,
            "tier1_status": tier1_status,
            "tier1_rule": tier1_rule,
            "tier1_message": tier1_message,
            "tier1_details": tier1_details,
            "tier2_status": tier2_status,
            "drift_score": drift_score,
            "drift_message": drift_message,
            "decision": "ALLOW",
            "reason": "",
            "estimated_usd_saved": 0.0,
            "latency_ms": 0.0,
        }

        graph_result = deterministic_circuit_graph.invoke(initial_state)

        end_ns = time.perf_counter_ns()
        latency_ms = round((end_ns - start_ns) / 1_000_000.0, 3)

        decision = graph_result["decision"]
        safe_reason = redact_string(graph_result["reason"])
        usd_saved = graph_result["estimated_usd_saved"]

        if decision == "HALT":
            self.total_simulated_usd_saved += usd_saved

        # Step 4: Emit Scrubbed OpenTelemetry Span Asynchronously (Fail-open / Fail-closed safe)
        span_data: Dict[str, Any]
        try:
            span_data = self.otel_emitter.emit_decision_span(
                trace_id_str=current_trace_id,
                tool_name=tool_name,
                decision=decision,
                mode=effective_mode,
                latency_ms=latency_ms,
                tier1_status=tier1_status,
                drift_score=drift_score,
                reason=safe_reason,
                estimated_usd_saved=usd_saved,
                arguments=arguments,
            )
        except Exception as exc:
            if not self.fail_open_tier3:
                raise
            logger.warning("Tier-3 OTel emission failed (fail-open active): %s", exc)
            span_data = {
                "name": f"traceops.guard.{tool_name}",
                "trace_id": current_trace_id,
                "tool_name": tool_name,
                "decision": decision,
                "mode": effective_mode,
                "latency_ms": latency_ms,
                "drift_score": drift_score,
                "reason": safe_reason,
                "arguments": redact_payload(arguments),
                "estimated_usd_saved": usd_saved,
                "sampled": False,
                "otel_error": "suppressed_fail_open",
            }

        action_taken: Literal["HALTED", "SUSPENDED", "PROCEEDED"] = (
            "HALTED"
            if (effective_mode == "enforce" and decision == "HALT")
            else ("SUSPENDED" if decision == "SUSPEND_HITL" else "PROCEEDED")
        )

        response_payload: Dict[str, Any] = {
            "trace_id": current_trace_id,
            "tool_name": tool_name,
            "decision": decision,
            "mode": effective_mode,
            "action_taken": action_taken,
            "reason": safe_reason,
            "tier1_status": tier1_status,
            "tier1_rule": tier1_rule,
            "drift_score": drift_score,
            "estimated_usd_saved": round(usd_saved, 4),
            "total_simulated_usd_saved": round(self.total_simulated_usd_saved, 4),
            "latency_ms": latency_ms,
            "otel_span": span_data,
        }

        # Step 5: Enforce vs Shadow Mode Action
        if effective_mode == "enforce" and decision == "HALT":
            logger.warning("[TraceOps ENFORCE HALT] %s (Latency: %s ms)", safe_reason, latency_ms)
            raise CircuitBreakerError(
                message=f"TraceOps Circuit Breaker Tripped: {safe_reason}",
                decision_record=response_payload,
            )

        logger.info(
            "[TraceOps %s] Decision: %s | Latency: %s ms",
            effective_mode.upper(),
            decision,
            latency_ms,
        )
        return response_payload
