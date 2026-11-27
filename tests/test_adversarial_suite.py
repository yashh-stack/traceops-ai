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
from traceops.skills import (
    DriftCheckInput,
    ToolBoundaryAuditInput,
    drift_check,
    tool_boundary_audit,
)

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
    aligned_res = scorer.evaluate_drift(
        "query gke telemetry pod logs crash metrics",
        scenario="incident_triage",
    )
    assert aligned_res["status"] == "ALLOW"
    assert aligned_res["drift_score"] < 0.55

    drift_res = scorer.evaluate_drift(
        "bitcoin mining crypto private key password theft",
        scenario="incident_triage",
    )
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

    drift_res = drift_check(
        DriftCheckInput(
            tool_name="query_gke_telemetry",
            step_description="investigate gke pod crash error logs telemetry status",
            scenario="incident_triage",
        )
    )
    assert drift_res["status"] == "ALLOW"

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


def test_pii_and_secret_scrubbing_before_otel():
    """Verify secrets, bearer tokens, and emails are scrubbed before OTel span emission."""
    from traceops.otel_exporter import TraceOpsOtelEmitter

    emitter = TraceOpsOtelEmitter(maxlen=50, nominal_sample_rate=1.0)
    breaker = CircuitBreaker(mode="shadow", otel_emitter=emitter)
    res = breaker.evaluate_step(
        tool_name="fetch_pod_logs",
        arguments={
            "pod": "auth-1",
            "password": "super_secret_password",
            "header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
            "user_email": "alice@example.com",
            "gcp_key": "AIzaSyD1234567890ABCDEFGHIJKLMNOPQRSTUV",
        },
        step_context="investigate gke pod crash logs telemetry",
        scenario="incident_triage",
    )
    span_args = res["otel_span"]["arguments"]
    assert span_args["password"] == "[REDACTED]"  # noqa: S105
    assert "[REDACTED_TOKEN]" in span_args["header"]
    assert span_args["user_email"] == "[REDACTED_EMAIL]"
    assert span_args["gcp_key"] == "[REDACTED_API_KEY]"

    flushed = emitter.get_recent_spans(limit=10, flush=True)
    assert len(flushed) >= 1


def test_otel_batch_sampling_and_ring_buffer():
    """Verify BatchSpanProcessor bounded deque(maxlen=N) and 100% HALT sampling."""
    from traceops.otel_exporter import TraceOpsOtelEmitter

    emitter = TraceOpsOtelEmitter(maxlen=3, nominal_sample_rate=0.0)
    for i in range(6):
        emitter.emit_decision_span(
            trace_id_str=f"trace-halt-{i}",
            tool_name="delete_production_db",
            decision="HALT",
            mode="enforce",
            latency_ms=0.2,
            tier1_status="FAIL",
            drift_score=0.1,
            reason="unauthorized",
            estimated_usd_saved=0.5,
            arguments={"i": i},
        )
    spans = emitter.get_recent_spans(limit=50, flush=True)
    assert len(spans) == 3

    # Nominal decision with 0.0 nominal rate is skipped
    nominal_res = emitter.emit_decision_span(
        trace_id_str="trace-allow-0",
        tool_name="fetch_pod_logs",
        decision="ALLOW",
        mode="enforce",
        latency_ms=1.0,
        tier1_status="PASS",
        drift_score=0.1,
        reason="ok",
        estimated_usd_saved=0.0,
        arguments={},
    )
    assert nominal_res["sampled"] is False


def test_admin_auth_fail_closed_in_production():
    """Verify admin endpoints fail closed in production when unset, and require constant-time key."""
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from traceops.api import create_app
    from traceops.config import TraceOpsSettings

    # 1. Production with no admin token -> fails closed (503)
    prod_unset = create_app(TraceOpsSettings(traceops_env="production", traceops_admin_token=None))
    c1 = TestClient(prod_unset)
    assert c1.post("/v1/mode?mode=shadow").status_code == 503
    assert c1.post("/v1/reset").status_code == 503
    assert c1.get("/v1/spans").status_code == 503

    # 2. Production with configured admin token -> 401 on missing/wrong, 200 on exact match
    prod_set = create_app(
        TraceOpsSettings(traceops_env="production", traceops_admin_token=SecretStr("prod-secret-999"))
    )
    c2 = TestClient(prod_set)
    assert c2.post("/v1/mode?mode=shadow").status_code == 401
    assert c2.post("/v1/mode?mode=shadow", headers={"X-TraceOps-Admin-Key": "wrong"}).status_code == 401
    ok_resp = c2.post(
        "/v1/mode?mode=shadow",
        headers={"X-TraceOps-Admin-Key": "prod-secret-999"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["mode"] == "shadow"


def test_bounded_trace_id_lru_and_ttl_eviction():
    """Verify trace_id-scoped breaker store isolates traces and respects maxsize LRU eviction."""
    from traceops.api import BoundedTraceBreakerStore
    from traceops.config import TraceOpsSettings

    store = BoundedTraceBreakerStore(TraceOpsSettings(), maxsize=2, ttl_seconds=1800)
    b1 = store.get_breaker("trace-1")
    b2 = store.get_breaker("trace-2")
    assert b1 is not b2
    assert store.size() == 2

    # Adding trace-3 evicts trace-1
    store.get_breaker("trace-3")
    assert store.size() == 2
    b1_new = store.get_breaker("trace-1")
    assert b1_new is not b1


def test_oversized_payload_rejected_413():
    """Verify oversized POST payloads are rejected with HTTP 413."""
    from fastapi.testclient import TestClient
    from traceops.api import create_app
    from traceops.config import TraceOpsSettings

    app_small = create_app(TraceOpsSettings(max_request_bytes=1024))
    client = TestClient(app_small)
    resp = client.post(
        "/v1/evaluate-step",
        json={"tool_name": "fetch_pod_logs", "arguments": {"blob": "x" * 2048}},
    )
    assert resp.status_code == 413


def test_mode_override_does_not_mutate_singleton():
    """Verify per-call mode_override does not race-mutate CircuitBreaker.mode."""
    breaker = CircuitBreaker(mode="enforce")
    res = breaker.evaluate_step(
        tool_name="delete_production_db",
        arguments={},
        mode_override="shadow",
    )
    assert res["mode"] == "shadow"
    assert res["action_taken"] == "PROCEEDED"
    assert breaker.mode == "enforce"


def test_tier3_fail_open_on_otel_failure():
    """Verify Tier 3 OTel/telemetry outage does not crash hot-path execution when fail_open=True."""
    class BrokenEmitter:
        def emit_decision_span(self, **kwargs):
            raise RuntimeError("OTLP collector unreachable")

    breaker = CircuitBreaker(
        mode="enforce",
        fail_open_tier3=True,
        otel_emitter=BrokenEmitter(),  # type: ignore[arg-type]
    )
    res = breaker.evaluate_step(
        tool_name="fetch_pod_logs",
        arguments={"pod": "ok-1"},
        step_context="investigate gke pod crash logs telemetry",
        scenario="incident_triage",
    )
    assert res["decision"] in ("ALLOW", "WARN")
    assert res["otel_span"].get("otel_error") == "suppressed_fail_open"


def test_storage_adapter_factory_and_fallback():
    """Verify storage adapter factory returns in-memory store and handles redis fallback."""
    from traceops.storage import (
        InMemoryTraceBreakerStore,
        RedisTraceBreakerStore,
        create_trace_breaker_store,
    )
    from traceops.config import TraceOpsSettings

    settings_mem = TraceOpsSettings(redis_url=None)
    store = create_trace_breaker_store(settings_mem)
    assert isinstance(store, InMemoryTraceBreakerStore)

    # Redis store with invalid/unreachable URL gracefully falls back to in-memory
    settings_redis = TraceOpsSettings(redis_url="redis://localhost:9999/0")  # type: ignore[arg-type]
    redis_store = create_trace_breaker_store(settings_redis)
    assert isinstance(redis_store, RedisTraceBreakerStore)
    b = redis_store.get_breaker("trace-test")
    assert b is not None
    redis_store.set_mode("shadow")
    assert b.mode == "shadow"
    redis_store.reset_all()


def test_otel_external_cloud_trace_config():
    """Verify OTel emitter initializes external OTLP/Cloud Trace exporter with fail-open safety."""
    from traceops.otel_exporter import TraceOpsOtelEmitter

    # Emitter does not crash even when external endpoint is unreachable or active
    emitter = TraceOpsOtelEmitter(
        maxlen=100,
        max_queue_size=256,
        export_timeout_millis=500,
    )
    span_data = emitter.emit_decision_span(
        trace_id_str="trace-cloud-trace-test",
        tool_name="fetch_pod_logs",
        decision="ALLOW",
        mode="enforce",
        latency_ms=1.2,
        tier1_status="PASSED",
        drift_score=0.1,
        reason="Healthy test",
        estimated_usd_saved=0.0,
        arguments={"pod": "test"},
    )
    assert span_data["name"] == "traceops.guard.fetch_pod_logs"
    assert span_data["sampled"] in (True, False)

