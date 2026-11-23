"""
Cloud Run-ready FastAPI Proxy for TraceOps AI.
Provides high-performance synchronous evaluation endpoint: POST /v1/evaluate-step
Latency budget: <15 ms synchronous response.
Dispatches background OTLP spans and evals off the critical path.
"""
from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Literal, Optional
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from traceops.circuit_breaker import CircuitBreaker, CircuitBreakerError
from traceops.otel_exporter import TraceOpsOtelEmitter

# Global Circuit Breaker Singleton
global_breaker = CircuitBreaker(
    mode=os.getenv("TRACEOPS_MODE", "enforce"),  # type: ignore
    max_identical_calls=int(os.getenv("MAX_IDENTICAL_CALLS", "3")),
    max_cost_usd=float(os.getenv("MAX_COST_USD", "0.50")),
    max_tokens=int(os.getenv("MAX_TOKENS", "25000")),
    drift_threshold=float(os.getenv("DRIFT_THRESHOLD", "0.55")),
)

app = FastAPI(
    title="TraceOps AI - Deterministic Circuit-Breaker API",
    description="Deterministic Agent Circuit-Breaker & Runtime Evals Engine (Google DeepMind x Cloud Startup Buildathon India 2026)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EvaluateStepRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool being executed by the agent")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments payload")
    step_cost_usd: float = Field(0.0, ge=0.0, description="Estimated USD cost of the step")
    step_tokens: int = Field(0, ge=0, description="Tokens consumed in the step")
    step_context: str = Field("", description="Natural language intent or context of the step")
    scenario: str = Field("default", description="Agent domain scenario (e.g. incident_triage)")
    trace_id: Optional[str] = Field(None, description="Correlating trace ID")
    mode: Optional[Literal["shadow", "enforce"]] = Field(None, description="Override execution mode")

class EvaluateStepResponse(BaseModel):
    trace_id: str
    tool_name: str
    decision: Literal["ALLOW", "WARN", "SUSPEND_HITL", "HALT"]
    mode: Literal["shadow", "enforce"]
    action_taken: Literal["HALTED", "SUSPENDED", "PROCEEDED"]
    reason: str
    tier1_status: str
    tier1_rule: Optional[str] = None
    drift_score: float
    estimated_usd_saved: float
    total_simulated_usd_saved: float
    latency_ms: float
    otel_span: Dict[str, Any]

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "service": "traceops-ai",
        "engine": "deterministic_circuit_breaker",
        "mode": global_breaker.mode,
        "hot_path_budget_ms": 15.0
    }

@app.post("/v1/evaluate-step", response_model=EvaluateStepResponse, tags=["Circuit Breaker"])
def evaluate_step(payload: EvaluateStepRequest):
    """
    Synchronous hot-path evaluation endpoint (<15 ms).
    Enforces deterministic safety invariants before tool execution.
    """
    # Temporarily set mode if per-request override provided
    original_mode = global_breaker.mode
    if payload.mode:
        global_breaker.set_mode(payload.mode)

    try:
        result = global_breaker.evaluate_step(
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            step_cost_usd=payload.step_cost_usd,
            step_tokens=payload.step_tokens,
            step_context=payload.step_context,
            scenario=payload.scenario,
            trace_id=payload.trace_id
        )
        return result
    except CircuitBreakerError as e:
        # In enforce mode, a HALT returns HTTP 403 Forbidden with decision telemetry
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "CIRCUIT_BREAKER_HALT",
                "message": e.message,
                **e.decision_record
            }
        )
    finally:
        if payload.mode:
            global_breaker.set_mode(original_mode)

@app.get("/v1/spans", tags=["Observability"])
def get_recent_spans(limit: int = 50):
    """Retrieve exported OpenTelemetry spans for observability and dashboard inspection."""
    emitter = TraceOpsOtelEmitter.get_instance()
    return {"spans": emitter.get_recent_spans(limit=limit)}

@app.post("/v1/mode", tags=["Configuration"])
def toggle_mode(mode: Literal["shadow", "enforce"]):
    """Toggle global circuit breaker execution mode."""
    global_breaker.set_mode(mode)
    return {"status": "SUCCESS", "mode": global_breaker.mode}

@app.post("/v1/reset", tags=["Configuration"])
def reset_breaker():
    """Reset the breaker state and history."""
    global_breaker.reset_trace()
    global_breaker.total_simulated_usd_saved = 0.0
    TraceOpsOtelEmitter.get_instance().clear()
    return {"status": "SUCCESS", "message": "Circuit breaker state reset."}
