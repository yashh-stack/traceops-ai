"""
TraceOps AI Circuit Breaker Core Engine.
Coordinates Tier-1 Deterministic Guard, Tier-2 Semantic Drift Scorer,
Tier-3 LangGraph State Machine, and background OTel emission.

Supports:
- mode="enforce": Raises CircuitBreakerError on HALT to terminate rogue agent executions.
- mode="shadow": Logs violations and tracks simulated USD saved without blocking execution.
"""
from __future__ import annotations
import time
import uuid
import logging
from typing import Any, Dict, List, Literal, Optional, Set, Type
from pydantic import BaseModel

from traceops.guards.deterministic import DeterministicGuard, Tier1Violation
from traceops.guards.semantic_drift import SemanticDriftScorer
from traceops.state_machine import deterministic_circuit_graph, CircuitState
from traceops.otel_exporter import TraceOpsOtelEmitter

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
    ):
        self.mode: Literal["shadow", "enforce"] = mode
        self.deterministic_guard = DeterministicGuard(
            max_identical_calls=max_identical_calls,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
            allowed_tools=allowed_tools,
            tool_schemas=tool_schemas,
        )
        self.drift_scorer = SemanticDriftScorer(
            drift_threshold=drift_threshold,
            warn_threshold=warn_threshold
        )
        self.otel_emitter = TraceOpsOtelEmitter.get_instance()
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
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single agent tool-call step on the synchronous hot path.
        Guarantees <15 ms latency target with 0 LLM calls.
        """
        start_ns = time.perf_counter_ns()
        current_trace_id = trace_id or str(uuid.uuid4())

        # Step 1: Tier-1 Deterministic Guard (<1 ms)
        tier1_status = "PASS"
        tier1_rule: Optional[str] = None
        tier1_message: Optional[str] = None
        tier1_details: Dict[str, Any] = {}

        try:
            self.deterministic_guard.evaluate_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                step_cost_usd=step_cost_usd,
                step_tokens=step_tokens
            )
        except Tier1Violation as v:
            tier1_status = "FAIL"
            tier1_rule = v.rule
            tier1_message = v.message
            tier1_details = v.details

        # Step 2: Tier-2 Semantic Drift Scorer (<5 ms)
        # Evaluated if Tier-1 passes or for full telemetry in shadow mode
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
            "mode": self.mode,
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
            "latency_ms": 0.0
        }

        graph_result = deterministic_circuit_graph.invoke(initial_state)

        end_ns = time.perf_counter_ns()
        latency_ms = round((end_ns - start_ns) / 1_000_000.0, 3)

        decision = graph_result["decision"]
        reason = graph_result["reason"]
        usd_saved = graph_result["estimated_usd_saved"]

        if decision == "HALT":
            self.total_simulated_usd_saved += usd_saved

        # Step 4: Emit OpenTelemetry Span Asynchronously
        span_data = self.otel_emitter.emit_decision_span(
            trace_id_str=current_trace_id,
            tool_name=tool_name,
            decision=decision,
            mode=self.mode,
            latency_ms=latency_ms,
            tier1_status=tier1_status,
            drift_score=drift_score,
            reason=reason,
            estimated_usd_saved=usd_saved,
            arguments=arguments
        )

        response_payload = {
            "trace_id": current_trace_id,
            "tool_name": tool_name,
            "decision": decision,
            "mode": self.mode,
            "action_taken": "HALTED" if (self.mode == "enforce" and decision == "HALT") else (
                "SUSPENDED" if decision == "SUSPEND_HITL" else "PROCEEDED"
            ),
            "reason": reason,
            "tier1_status": tier1_status,
            "tier1_rule": tier1_rule,
            "drift_score": drift_score,
            "estimated_usd_saved": round(usd_saved, 4),
            "total_simulated_usd_saved": round(self.total_simulated_usd_saved, 4),
            "latency_ms": latency_ms,
            "otel_span": span_data
        }

        # Step 5: Enforce vs Shadow Mode Action
        if self.mode == "enforce" and decision == "HALT":
            logger.warning(f"[TraceOps ENFORCE HALT] {reason} (Latency: {latency_ms} ms)")
            raise CircuitBreakerError(
                message=f"TraceOps Circuit Breaker Tripped: {reason}",
                decision_record=response_payload
            )

        logger.info(f"[TraceOps {self.mode.upper()}] Decision: {decision} | Latency: {latency_ms} ms")
        return response_payload
