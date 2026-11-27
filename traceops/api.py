"""
Cloud Run-ready FastAPI Proxy for TraceOps AI.
Hardened with:
- Validated pydantic-settings configuration
- Bounded LRU+TTL per-trace breaker state cache (maxsize=10000, ttl=1800s)
- Fail-closed constant-time X-TraceOps-Admin-Key auth on /v1/mode, /v1/reset, /v1/spans
- Restricted CORS origins, 64 KB payload size cap, per-IP rate limiting, sanitized 500s
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from traceops.circuit_breaker import CircuitBreakerError
from traceops.config import TraceOpsSettings, get_settings
from traceops.otel_exporter import TraceOpsOtelEmitter
from traceops.security import SlidingWindowRateLimiter, verify_admin_token
from traceops.storage import (
    BaseTraceBreakerStore,
    BoundedTraceBreakerStore,
    InMemoryTraceBreakerStore,
    create_trace_breaker_store,
)

__all__ = [
    "app",
    "create_app",
    "BoundedTraceBreakerStore",
    "InMemoryTraceBreakerStore",
    "BaseTraceBreakerStore",
    "create_trace_breaker_store",
]

logger = logging.getLogger("traceops.api")



_settings = get_settings()
trace_store = create_trace_breaker_store(_settings)
# Backward-compatible alias pointing at default breaker
global_breaker = trace_store.get_breaker(None)
_rate_limiter = SlidingWindowRateLimiter(max_requests_per_minute=_settings.rate_limit_rpm)


def create_app(settings: Optional[TraceOpsSettings] = None) -> FastAPI:
    """Application factory supporting isolated security & settings tests."""
    active_settings = settings or get_settings()
    local_store = (
        trace_store
        if settings is None
        else create_trace_breaker_store(active_settings)
    )
    local_limiter = (
        _rate_limiter
        if settings is None
        else SlidingWindowRateLimiter(max_requests_per_minute=active_settings.rate_limit_rpm)
    )

    application = FastAPI(
        title="TraceOps AI - Deterministic Circuit-Breaker API",
        description=(
            "Deterministic Agent Circuit-Breaker & Runtime Evals Engine "
            "(Google DeepMind x Cloud Startup Buildathon India 2026)"
        ),
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-TraceOps-Admin-Key"],
    )

    @application.middleware("http")
    async def enforce_payload_and_rate_limits(request: Request, call_next: Any) -> Any:
        # 1. Request payload size cap (check header & stream body if needed)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > active_settings.max_request_bytes:
                    max_b = active_settings.max_request_bytes
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds {max_b} bytes limit.",
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "INVALID_CONTENT_LENGTH", "message": "Invalid Content-Length header."},
                )

        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > active_settings.max_request_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={
                        "error": "PAYLOAD_TOO_LARGE",
                        "message": f"Request body exceeds {active_settings.max_request_bytes} bytes limit.",
                    },
                )

        # 2. Per-IP sliding-window rate limit
        client_ip = request.client.host if request.client else "unknown"
        if not local_limiter.allow(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many requests."},
            )

        return await call_next(request)

    @application.exception_handler(Exception)
    async def sanitized_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )

    def _require_admin(x_traceops_admin_key: Optional[str]) -> Optional[JSONResponse]:
        ok, code, msg = verify_admin_token(x_traceops_admin_key, active_settings)
        if not ok:
            return JSONResponse(status_code=code, content={"error": "ADMIN_AUTH_REQUIRED", "message": msg})
        return None

    @application.get("/health", tags=["System"])
    def health_check() -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "service": "traceops-ai",
            "engine": "deterministic_circuit_breaker",
            "mode": local_store.default_mode,
            "hot_path_budget_ms": 15.0,
            "active_trace_contexts": local_store.size(),
        }

    @application.post(
        "/v1/evaluate-step",
        response_model=EvaluateStepResponse,
        tags=["Circuit Breaker"],
    )
    def evaluate_step(payload: EvaluateStepRequest) -> Any:
        """
        Synchronous hot-path evaluation endpoint (<15 ms).
        Uses bounded trace_id context + non-mutating mode override.
        """
        breaker = local_store.get_breaker(payload.trace_id)
        try:
            return breaker.evaluate_step(
                tool_name=payload.tool_name,
                arguments=payload.arguments,
                step_cost_usd=payload.step_cost_usd,
                step_tokens=payload.step_tokens,
                step_context=payload.step_context,
                scenario=payload.scenario,
                trace_id=payload.trace_id,
                mode_override=payload.mode,
            )
        except CircuitBreakerError as e:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "CIRCUIT_BREAKER_HALT",
                    "message": e.message,
                    **e.decision_record,
                },
            )

    @application.get("/v1/spans", tags=["Observability"])
    def get_recent_spans(
        limit: int = 50,
        x_traceops_admin_key: Optional[str] = Header(default=None, alias="X-TraceOps-Admin-Key"),
    ) -> Any:
        """Retrieve scrubbed OpenTelemetry spans (admin auth enforced in production / when configured)."""
        auth_err = _require_admin(x_traceops_admin_key)
        if auth_err is not None:
            return auth_err
        emitter = TraceOpsOtelEmitter.get_instance()
        bounded_limit = max(1, min(limit, 500))
        return {"spans": emitter.get_recent_spans(limit=bounded_limit)}

    @application.post("/v1/mode", tags=["Configuration"])
    def toggle_mode(
        mode: Literal["shadow", "enforce"],
        x_traceops_admin_key: Optional[str] = Header(default=None, alias="X-TraceOps-Admin-Key"),
    ) -> Any:
        """Toggle global circuit breaker execution mode (fail-closed admin auth)."""
        auth_err = _require_admin(x_traceops_admin_key)
        if auth_err is not None:
            return auth_err
        local_store.set_mode(mode)
        return {"status": "SUCCESS", "mode": local_store.default_mode}

    @application.post("/v1/reset", tags=["Configuration"])
    def reset_breaker(
        x_traceops_admin_key: Optional[str] = Header(default=None, alias="X-TraceOps-Admin-Key"),
    ) -> Any:
        """Reset all breaker state and OTel ring buffer (fail-closed admin auth)."""
        auth_err = _require_admin(x_traceops_admin_key)
        if auth_err is not None:
            return auth_err
        local_store.reset_all()
        TraceOpsOtelEmitter.get_instance().clear()
        return {"status": "SUCCESS", "message": "Circuit breaker state reset."}

    return application


class EvaluateStepRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=128, description="Name of the tool being executed")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments payload")
    step_cost_usd: float = Field(0.0, ge=0.0, description="Estimated USD cost of the step")
    step_tokens: int = Field(0, ge=0, description="Tokens consumed in the step")
    step_context: str = Field("", max_length=4096, description="Natural language intent or context")
    scenario: str = Field("default", max_length=64, description="Agent domain scenario")
    trace_id: Optional[str] = Field(None, max_length=128, description="Correlating trace ID")
    mode: Optional[Literal["shadow", "enforce"]] = Field(None, description="Per-request mode override")


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


app = create_app()
