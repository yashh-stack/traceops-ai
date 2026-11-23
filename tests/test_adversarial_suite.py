"""
TraceOps AI Adversarial Verification Suite.
Rigorous verification for Google DeepMind x Cloud Startup Buildathon India 2026.

Validates:
1. Exact runaway tool-call loop detection in <1 ms.
2. Unauthorized tool-call interception by least-privilege allowlist.
3. Execution mode toggle: SHADOW mode logs without blocking; ENFORCE mode actively halts.
4. Semantic goal drift detection & threshold enforcement.
5. In-process decorator (@traceops.guard) integration.
6. Rigorous p95 hot-path latency benchmark assertion (<15 ms).
"""
import time
import pytest
from pydantic import BaseModel, Field

from traceops.circuit_breaker import CircuitBreaker, CircuitBreakerError
from traceops.guards.deterministic import DeterministicGuard, Tier1Violation
from traceops.guards.semantic_drift import SemanticDriftScorer
from traceops.decorator import guard
from traceops.skills import drift_check, tool_boundary_audit, DriftCheckInput, ToolBoundaryAuditInput

class QueryArgsSchema(BaseModel):
    cluster: str = Field(..., min_length=2)
    metric: str = Field(...)

def test_tier1_runaway_loop_caught_under_1ms():
    """Verify exact duplicate tool-call hash detector catches loop in <1 ms."""
    guard = DeterministicGuard(max_identical_calls=3)
    tool = "query_gke_telemetry"
    args = {"cluster": "prod-india", "metric": "cpu_utilization"}

    # Call 1 & 2 pass
    guard.evaluate_tool_call(tool, args)
    guard.evaluate_tool_call(tool, args)

    # Call 3 triggers violation
    start_ns = time.perf_counter_ns()
    with pytest.raises(Tier1Violation) as exc_info:
        guard.evaluate_tool_call(tool, args)
    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

    assert "runaway_loop" in exc_info.value.rule
    assert elapsed_ms < 1.0, f"Runaway loop check exceeded 1 ms: {elapsed_ms:.4f} ms"

def test_unauthorized_tool_blocked_by_allowlist():
    """Verify unauthorized or destructive tools are blocked."""
    breaker = CircuitBreaker(mode="enforce")
    with pytest.raises(CircuitBreakerError) as exc_info:
        breaker.evaluate_step(
            tool_name="delete_production_db",
            arguments={"database": "prod_orders", "force": True}
        )

    rec = exc_info.value.decision_record
    assert rec["decision"] == "HALT"
    assert rec["tier1_status"] == "FAIL"
    assert rec["tier1_rule"] == "unauthorized_tool"
    assert "least-privilege allowlist" in rec["reason"]

def test_shadow_vs_enforce_mode():
    """Verify SHADOW mode records simulated savings without raising; ENFORCE halts."""
    breaker_shadow = CircuitBreaker(mode="shadow")
    shadow_res = breaker_shadow.evaluate_step(
        tool_name="delete_production_db",
        arguments={"database": "prod_orders"}
    )
    assert shadow_res["decision"] == "HALT"
    assert shadow_res["action_taken"] == "PROCEEDED"
    assert shadow_res["estimated_usd_saved"] > 0.0

    breaker_enforce = CircuitBreaker(mode="enforce")
    with pytest.raises(CircuitBreakerError) as exc_info:
        breaker_enforce.evaluate_step(
            tool_name="delete_production_db",
            arguments={"database": "prod_orders"}
        )
    assert exc_info.value.decision_record["action_taken"] == "HALTED"

def test_schema_validation_guard():
    """Verify Pydantic schema validation catches invalid arguments."""
    guard = DeterministicGuard(
        allowed_tools={"query_gke_telemetry"},
        tool_schemas={"query_gke_telemetry": QueryArgsSchema}
    )

    # Valid arguments
    guard.evaluate_tool_call("query_gke_telemetry", {"cluster": "gke-prod", "metric": "cpu"})

    # Invalid arguments (missing required field)
    with pytest.raises(Tier1Violation) as exc_info:
        guard.evaluate_tool_call("query_gke_telemetry", {"cluster": "gke-prod"})
    assert exc_info.value.rule == "schema_validation_error"

def test_cost_budget_ceiling_enforced():
    """Verify hard cumulative USD ceiling triggers HALT."""
    breaker = CircuitBreaker(mode="enforce", max_cost_usd=0.10)
    # Step 1 within budget ($0.06 <= $0.10)
    res1 = breaker.evaluate_step(
        tool_name="fetch_pod_logs",
        arguments={"pod": "pod-1"},
        step_cost_usd=0.06,
        step_context="investigate gke pod crash error logs for service telemetry",
        scenario="incident_triage"
    )
    assert res1["decision"] == "ALLOW"

    # Step 2 breaches budget ($0.06 + $0.06 = $0.12 > $0.10)
    with pytest.raises(CircuitBreakerError) as exc_info:
        breaker.evaluate_step(
            tool_name="fetch_pod_logs",
            arguments={"pod": "pod-2"},
            step_cost_usd=0.06,
            step_context="investigate gke pod crash error logs for service telemetry",
            scenario="incident_triage"
        )
    assert exc_info.value.decision_record["tier1_rule"] == "cost_ceiling_exceeded"

def test_semantic_drift_scorer():
    """Verify in-process cosine similarity detects off-topic drift."""
    scorer = SemanticDriftScorer(drift_threshold=0.55)
    aligned_res = scorer.evaluate_drift("query gke telemetry pod logs crash metrics", scenario="incident_triage")
    assert aligned_res["status"] == "ALLOW"
    assert aligned_res["drift_score"] < 0.55

    drift_res = scorer.evaluate_drift("bitcoin mining crypto private key password theft", scenario="incident_triage")
    assert drift_res["status"] in ("HALT", "WARN")
    assert drift_res["drift_score"] >= 0.40

def test_decorator_guard_enforce_and_shadow():
    """Verify @traceops.guard decorator transparently protects functions."""
    @guard(
        mode="enforce",
        scenario="incident_triage"
    )
    def fetch_pod_logs(pod: str, namespace: str = "default"):
        return f"logs for {pod}"

    # Safe call succeeds
    result = fetch_pod_logs(pod="frontend-1")
    assert result == "logs for frontend-1"

    # Unauthorized function name trips breaker
    @guard(mode="enforce")
    def drop_table(table: str):
        return "dropped"

    with pytest.raises(CircuitBreakerError):
        drop_table(table="users")

def test_agent_skills_export():
    """Verify Google Agent Skills drift_check and tool_boundary_audit."""
    audit_safe = tool_boundary_audit(ToolBoundaryAuditInput(tool_name="query_gke_telemetry"))
    assert audit_safe["compliant"] is True
    assert audit_safe["decision"] == "PERMITTED"

    audit_attack = tool_boundary_audit(ToolBoundaryAuditInput(tool_name="drop_database"))
    assert audit_attack["compliant"] is False
    assert audit_attack["decision"] == "BLOCKED"

def test_hot_path_p95_latency_benchmark():
    """
    CRITICAL ARCHITECTURAL ASSERTION:
    Hot path must evaluate synchronously and satisfy p95 latency < 15.0 ms.
    """
    breaker = CircuitBreaker(mode="enforce")
    warmup_count = 10
    benchmark_count = 50
    latencies = []

    # Warmup to JIT compile and prime caches
    for i in range(warmup_count):
        breaker.evaluate_step(
            tool_name="fetch_pod_logs",
            arguments={"pod": f"pod-warmup-{i}"},
            step_context="investigate gke pod crash error logs for service telemetry",
            scenario="incident_triage"
        )

    # Benchmark loop
    for i in range(benchmark_count):
        start_ns = time.perf_counter_ns()
        breaker.evaluate_step(
            tool_name="fetch_pod_logs",
            arguments={"pod": f"pod-bench-{i}"},
            step_context="investigate gke pod crash error logs for service telemetry",
            scenario="incident_triage"
        )
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        latencies.append(elapsed_ms)

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"\n[BENCHMARK] p50: {p50:.2f} ms | p95: {p95:.2f} ms | p99: {p99:.2f} ms")
    assert p95 < 15.0, f"Hot-path p95 latency violation: {p95:.2f} ms >= 15.0 ms target"
