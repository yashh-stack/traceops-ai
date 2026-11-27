# ⚡ TraceOps AI

> **Deterministic Agent Circuit-Breaker & Runtime Evals Engine**  
> *Apache 2.0 Open-Core Infrastructure for Multi-Agent Systems (LangGraph, AutoGen, MCP)*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Deterministic_State_Machine-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Batch_OTLP-black.svg)](https://opentelemetry.io/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://www.apache.org/licenses/LICENSE-2.0)

---

## Core Architectural Invariant

> **"LLMs advise. The deterministic state machine decides."**

- **Hot Path (`< 15 ms` SLO on CPU, zero LLM calls):** Tier 1 deterministic hash loop detector, cumulative USD/token budget ceilings, least-privilege tool allowlist, Pydantic argument validation, PII/secret redaction, and Tier 2 in-process cosine drift scoring against cached centroids.
- **Async Cold Path (`0 ms` hot-path overhead):** Tail-biased OpenTelemetry `BatchSpanProcessor` (`10%` nominal, `100%` halted/HITL, bounded `maxlen=500` ring buffer) paired with async `gemini-3.5-flash-lite` judge exporting DeepEval JSONL cases.
- **Offline Baseline Builder:** Synthesizes golden trajectories via `gemini-3.8-flash` and refreshes optional Cloud SQL `pgvector` / local centroid cache.

---

## 5-Line Quickstart (`SHADOW` -> `ENFORCE`)

```bash
git clone https://github.com/yashh-stack/traceops-ai.git && cd traceops-ai && pip install -e .
```

```python
from traceops import guard, CircuitBreakerError

# Start in SHADOW (audit savings safely), flip to ENFORCE to actively halt rogue steps
@guard(mode="shadow", max_cost_usd=0.50, scenario="incident_triage")
def fetch_pod_logs(pod: str):
    return f"logs:{pod}"
```

Flip `mode="enforce"` (or `TRACEOPS_MODE=enforce`) to raise `CircuitBreakerError` (and HTTP `403 CIRCUIT_BREAKER_HALT` on the proxy) mid-flight when a loop, unauthorized tool, budget breach, or policy drift occurs.

---

## Verified Benchmarks

Measured locally on CPU (`scripts/run_benchmark.py`, 200 hot-path evaluations):

| Metric | Measured Result | SLO / Baseline |
| :--- | :--- | :--- |
| **Tier 1 Loop Interception** | `0.0534 ms` | `< 1.0 ms` |
| **Hot-Path p50 / p95 / p99** | `4.11 ms` / `6.37 ms` / `12.84 ms` | p95 `< 15.0 ms` (`23.85x` faster vs `152 ms` GPU SLM) |
| **Adversarial Test Suite** | `9/9` passed (`0` warnings) | `100%` pass gate |
| **Dependency Audit (`pip-audit`)** | `0` known CVEs | `0` Critical/High |

*(See Phase 5 Verification Report for updated post-hardening numbers).*

---

## Production Security & Privacy Disclosure

- **Tier 1 Secret & PII Redaction:** API keys (`AIza...`, `sk-...`, `ghp_...`), Bearer tokens, DB credential URIs, emails, and sensitive dictionary keys (`password`, `token`, `secret`, `api_key`) are scrubbed in-process *before* OTLP span export, logs, or API telemetry responses.
- **Fail-Closed Admin Controls:** `POST /v1/mode`, `POST /v1/reset`, and `GET /v1/spans` enforce constant-time `X-TraceOps-Admin-Key` verification via `hmac.compare_digest`. When `TRACEOPS_ENV=production` and `TRACEOPS_ADMIN_TOKEN` is unset, admin endpoints fail closed (`HTTP 503`).
- **Bounded Memory & Concurrency:** Per-`trace_id` breaker states live in a thread-safe LRU+TTL cache (`maxsize=10000`, `ttl=1800s`), HTTP bodies are capped at `64 KB` (`413`), and sliding-window rate limiting guards against DoS.
- **Reporting Vulnerabilities:** Do not open public GitHub issues for security flaws. Report privately to repository maintainers or via GitHub Security Advisories (`yashh-stack/traceops-ai`).
- **License:** Apache 2.0.
