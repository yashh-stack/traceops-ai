import time
import json
from fastapi.testclient import TestClient
from traceops.api import app

def run_suite():
    client = TestClient(app)

    print("============================================================")
    print("⚡ TraceOps AI Full End-to-End HTTP Proxy Suite")
    print("============================================================")

    # 1. Health
    t0 = time.perf_counter()
    r = client.get("/health")
    lat = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    print(f"[1/7] GET /health                 -> {r.status_code} ({lat:.2f} ms) | {r.json()['status']}")

    # 2. Reset breaker state
    client.post("/v1/reset")

    # 3. In-Policy Allowed Step
    t0 = time.perf_counter()
    payload_allow = {
        "tool_name": "fetch_pod_logs",
        "arguments": {"pod": "auth-service-pod"},
        "step_description": "Investigate cluster errors",
        "goal": "Debug production cluster pod crash"
    }
    r = client.post("/v1/evaluate-step", json=payload_allow)
    lat = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    data = r.json()
    print(f"[2/7] POST /v1/evaluate (Allow)   -> {r.status_code} ({lat:.2f} ms) | decision={data['decision']}, drift={data['drift_score']:.4f}")

    # 4. Unauthorized Tool Block (delete_production_db)
    t0 = time.perf_counter()
    payload_unauth = {
        "tool_name": "delete_production_db",
        "arguments": {"force": True}
    }
    r = client.post("/v1/evaluate-step", json=payload_unauth)
    lat = (time.perf_counter() - t0) * 1000
    assert r.status_code == 403
    data = r.json()
    print(f"[3/7] POST /v1/evaluate (Block)   -> {r.status_code} ({lat:.2f} ms) | error={data['error']}, decision={data['decision']}")

    # 5. Runaway Loop Interception
    client.post("/v1/reset")
    loop_lat = 0.0
    for i in range(4):
        t0 = time.perf_counter()
        r = client.post("/v1/evaluate-step", json={"tool_name": "query_gke_telemetry", "arguments": {"query": "cpu"}})
        loop_lat = (time.perf_counter() - t0) * 1000
    assert r.status_code == 403
    data = r.json()
    print(f"[4/7] Runaway Loop Intercept      -> {r.status_code} ({loop_lat:.2f} ms) | decision={data['decision']}, reason={data['reason'][:40]}...")

    # 6. HITL High-Value Refund
    client.post("/v1/reset")
    payload_hitl = {
        "tool_name": "refund_user",
        "arguments": {"amount": 2500.0, "user_id": "usr_99"}
    }
    r = client.post("/v1/evaluate-step", json=payload_hitl)
    assert r.status_code == 200
    data = r.json()
    print(f"[5/7] High-Value Refund (HITL)    -> {r.status_code} | decision={data['decision']} (Threshold: >$500)")

    # 7. Mode switch to shadow
    r = client.post("/v1/mode?mode=shadow")
    assert r.status_code == 200
    print(f"[6/7] Mode Switch (SHADOW)        -> {r.status_code} | mode={r.json()['mode']}")

    # In shadow mode, unauthorized tool doesn't halt with 403, it logs with 200
    r = client.post("/v1/evaluate-step", json=payload_unauth)
    assert r.status_code == 200
    data = r.json()
    print(f"[7/7] SHADOW Mode Logging         -> {r.status_code} | action={data['action_taken']}, saved_usd=${data['estimated_usd_saved']}")

    # Reset back to enforce
    client.post("/v1/mode?mode=enforce")
    client.post("/v1/reset")
    print("============================================================")
    print("✅ All 7 End-to-End API Scenarios Verified Successfully!")
    print("============================================================")

if __name__ == "__main__":
    run_suite()
