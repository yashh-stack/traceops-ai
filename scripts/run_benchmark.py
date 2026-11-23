#!/usr/bin/env python
"""
Real-Time Benchmark Export for TraceOps AI.
Runs 200 synthetic hot-path evaluations, records latency metrics (p50, p90, p95, p99, max),
validates Tier-1 loop interception speed, and compares vs GPU SLM baseline (152 ms).
Outputs benchmark_report.json.
"""
import os
import sys
import time
import json
import numpy as np

# Ensure root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from traceops.circuit_breaker import CircuitBreaker, CircuitBreakerError
from traceops.guards.deterministic import DeterministicGuard, Tier1Violation

def run_benchmark():
    print("=" * 60)
    print("⚡ Running TraceOps AI Hot-Path Latency Benchmark (200 Iterations)")
    print("=" * 60)

    breaker = CircuitBreaker(mode="enforce", max_cost_usd=100.0, max_tokens=1000000)

    # 1. Warm-up (10 calls)
    for i in range(10):
        breaker.evaluate_step(
            tool_name="fetch_pod_logs",
            arguments={"pod": f"warmup-{i}", "tail": 50},
            step_context="triage gke pod crash errors and pull telemetry",
            scenario="incident_triage"
        )

    # 2. Benchmark Loop (200 evaluations)
    latencies_ms = []
    scenarios_and_context = [
        ("incident_triage", "fetch_pod_logs", "investigate gke pod crash error logs for service telemetry"),
        ("incident_triage", "query_gke_telemetry", "query gke cluster telemetry status and error rates"),
        ("canary_deployment", "run_canary_test", "canary deployment rollout traffic shift verify error budget"),
        ("resource_scaling", "get_service_metrics", "scale hpa cpu memory limits replica utilization metrics"),
    ]

    for i in range(200):
        scenario, tool, ctx = scenarios_and_context[i % len(scenarios_and_context)]
        args = {"item_id": f"trace-{i}", "metric": "cpu", "timestamp": time.time()}

        start_ns = time.perf_counter_ns()
        res = breaker.evaluate_step(
            tool_name=tool,
            arguments=args,
            step_cost_usd=0.005,
            step_tokens=150,
            step_context=ctx,
            scenario=scenario
        )
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        latencies_ms.append(elapsed_ms)

    latencies_ms.sort()
    p50 = float(np.percentile(latencies_ms, 50))
    p90 = float(np.percentile(latencies_ms, 90))
    p95 = float(np.percentile(latencies_ms, 95))
    p99 = float(np.percentile(latencies_ms, 99))
    max_lat = float(np.max(latencies_ms))
    mean_lat = float(np.mean(latencies_ms))

    # 3. Tier-1 Loop Interception Benchmark
    guard = DeterministicGuard(max_identical_calls=3)
    loop_tool = "query_gke_telemetry"
    loop_args = {"cluster": "asia-south1", "type": "heartbeat"}
    guard.evaluate_tool_call(loop_tool, loop_args)
    guard.evaluate_tool_call(loop_tool, loop_args)

    t0 = time.perf_counter_ns()
    try:
        guard.evaluate_tool_call(loop_tool, loop_args)
    except Tier1Violation:
        pass
    tier1_loop_interception_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

    # 4. Comparison vs GPU Small Language Model (SLM) baseline
    gpu_slm_baseline_ms = 152.0
    speedup_factor = round(gpu_slm_baseline_ms / p95, 2)
    latency_reduction_pct = round(((gpu_slm_baseline_ms - p95) / gpu_slm_baseline_ms) * 100, 2)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iterations": 200,
        "slo_target_ms": 15.0,
        "slo_achieved": bool(p95 < 15.0),
        "latency_metrics_ms": {
            "p50": round(p50, 3),
            "p90": round(p90, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "mean": round(mean_lat, 3),
            "max": round(max_lat, 3)
        },
        "tier1_benchmarks_ms": {
            "exact_loop_interception_ms": round(tier1_loop_interception_ms, 4),
            "sub_1ms_slo_met": bool(tier1_loop_interception_ms < 1.0)
        },
        "industry_comparison": {
            "gpu_slm_guardrail_baseline_ms": gpu_slm_baseline_ms,
            "traceops_p95_ms": round(p95, 3),
            "speedup_vs_gpu_slm": f"{speedup_factor}x faster",
            "latency_reduction_percentage": f"{latency_reduction_pct}%"
        }
    }

    output_path = os.path.join(PROJECT_ROOT, "benchmark_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n✅ Benchmark Complete!")
    print(f"p50 Latency:  {p50:.2f} ms")
    print(f"p95 Latency:  {p95:.2f} ms  (SLO < 15.0 ms: {p95 < 15.0})")
    print(f"p99 Latency:  {p99:.2f} ms")
    print(f"Tier-1 Catch: {tier1_loop_interception_ms:.4f} ms (SLO < 1.0 ms: {tier1_loop_interception_ms < 1.0})")
    print(f"Speedup vs 152ms GPU SLM: {speedup_factor}x faster ({latency_reduction_pct}% reduction)")
    print(f"Saved report to: {output_path}")

    assert p95 < 15.0, f"Latency violation: p95 {p95:.2f} ms >= 15.0 ms"
    assert tier1_loop_interception_ms < 1.0, f"Tier 1 violation: {tier1_loop_interception_ms:.2f} ms >= 1.0 ms"

if __name__ == "__main__":
    run_benchmark()
