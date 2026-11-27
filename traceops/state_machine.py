"""
Tier-3 Deterministic LangGraph State Machine for TraceOps AI.
Invariant: "LLMs advise. The deterministic state machine decides."

Evaluates Tier-1 (deterministic rules) and Tier-2 (semantic drift) telemetry
and deterministically transitions through states to reach terminal policy:
ALLOW, WARN, or HALT.
Zero LLM calls during graph traversal.
"""
from __future__ import annotations
from typing import Any, Dict, Literal, Optional, TypedDict
from langgraph.graph import StateGraph, END
import traceops.shims  # noqa: F401  # Install Windows DLL shims before langgraph imports

class CircuitState(TypedDict):
    """Execution state of the circuit breaker step evaluation."""
    # Inputs
    tool_name: str
    arguments: Dict[str, Any]
    step_cost_usd: float
    step_tokens: int
    step_context: str
    scenario: str
    mode: Literal["shadow", "enforce"]

    # Tier Evaluation Results
    tier1_status: Literal["PASS", "FAIL"]
    tier1_rule: Optional[str]
    tier1_message: Optional[str]
    tier1_details: Dict[str, Any]

    tier2_status: Literal["ALLOW", "WARN", "HALT"]
    drift_score: float
    drift_message: Optional[str]

    # Final Decision Output
    decision: Literal["ALLOW", "WARN", "SUSPEND_HITL", "HALT"]
    reason: str
    estimated_usd_saved: float
    latency_ms: float

def evaluate_tier1_node(state: CircuitState) -> Dict[str, Any]:
    """Node 1: Evaluates Tier-1 Deterministic check results."""
    return {}

def evaluate_tier2_node(state: CircuitState) -> Dict[str, Any]:
    """Node 2: Evaluates Tier-2 Semantic drift score."""
    return {}

def decide_terminal_policy(state: CircuitState) -> Dict[str, Any]:
    """
    Node 3: Pure deterministic policy arbiter.
    Computes final decision: ALLOW / WARN / SUSPEND_HITL / HALT.
    Calculates estimated USD saved if a rogue execution is halted.
    """
    t1_status = state.get("tier1_status", "PASS")
    t2_status = state.get("tier2_status", "ALLOW")
    tool_name = state.get("tool_name", "")
    args = state.get("arguments", {})

    # Priority 1: Tier-1 Hard Violations always demand HALT
    if t1_status == "FAIL":
        decision = "HALT"
        reason = f"Tier-1 Deterministic Violation: {state.get('tier1_rule', 'unknown')} - {state.get('tier1_message', '')}"
        est_savings = max(0.25, state.get("step_cost_usd", 0.0) * 10)
    elif t2_status == "HALT":
        decision = "HALT"
        reason = f"Tier-2 Goal Drift Breach: {state.get('drift_message', '')}"
        est_savings = 0.50
    # Priority 2: Human-in-the-Loop Suspend trigger for high-stakes financial or risky operations
    elif tool_name in ("refund_user", "issue_credit", "modify_iam_policy") and (
        float(args.get("amount", 0.0)) > 500.0 or bool(args.get("high_risk", False))
    ):
        amount = float(args.get("amount", 0.0))
        decision = "SUSPEND_HITL"
        reason = f"HITL Policy Enforced: Tool '{tool_name}' involves high-stakes value (${amount:.2f} > $500.00). Execution suspended awaiting human sign-off."
        est_savings = amount
    elif t2_status == "WARN":
        decision = "WARN"
        reason = f"Tier-2 Goal Drift Warning: {state.get('drift_message', '')}"
        est_savings = 0.0
    else:
        decision = "ALLOW"
        reason = "All deterministic invariant checks and semantic alignments passed."
        est_savings = 0.0

    return {
        "decision": decision,
        "reason": reason,
        "estimated_usd_saved": est_savings
    }

def route_after_tier1(state: CircuitState) -> str:
    """Conditional edge: If Tier-1 fails, short-circuit directly to policy decision."""
    if state.get("tier1_status") == "FAIL":
        return "decide_terminal_policy"
    return "evaluate_tier2_node"

def build_circuit_breaker_graph():
    """Compile and return the deterministic LangGraph state machine."""
    workflow = StateGraph(CircuitState)

    workflow.add_node("evaluate_tier1_node", evaluate_tier1_node)
    workflow.add_node("evaluate_tier2_node", evaluate_tier2_node)
    workflow.add_node("decide_terminal_policy", decide_terminal_policy)

    workflow.set_entry_point("evaluate_tier1_node")

    workflow.add_conditional_edges(
        "evaluate_tier1_node",
        route_after_tier1,
        {
            "decide_terminal_policy": "decide_terminal_policy",
            "evaluate_tier2_node": "evaluate_tier2_node"
        }
    )

    workflow.add_edge("evaluate_tier2_node", "decide_terminal_policy")
    workflow.add_edge("decide_terminal_policy", END)

    return workflow.compile()

# Global compiled graph singleton for zero overhead
deterministic_circuit_graph = build_circuit_breaker_graph()
