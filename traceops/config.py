"""
Validated configuration management for TraceOps AI using pydantic-settings.
Loads configuration from environment variables and optional .env files
without hardcoding secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TraceOpsSettings(BaseSettings):
    """Central validated settings for TraceOps AI runtime and API proxy."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    traceops_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment; 'production' enforces fail-closed admin auth.",
    )
    traceops_mode: Literal["shadow", "enforce"] = Field(
        default="enforce",
        description="Circuit-breaker execution mode.",
    )

    # Tier 1 Deterministic Guard limits
    max_identical_calls: int = Field(default=3, ge=1, le=1000)
    max_cost_usd: float = Field(default=0.50, ge=0.0)
    max_tokens: int = Field(default=25000, ge=0)

    # Tier 2 Semantic Drift thresholds
    drift_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    warn_threshold: float = Field(default=0.40, ge=0.0, le=1.0)

    # Bounded Trace State Cache (prevents unbounded growth in long-lived containers)
    trace_cache_maxsize: int = Field(default=10000, ge=100, le=1000000)
    trace_cache_ttl_seconds: int = Field(default=1800, ge=30, le=86400)

    # Tier 3 OTLP & Async Judge configuration
    otel_nominal_sample_rate: float = Field(default=0.10, ge=0.0, le=1.0)
    otel_ring_buffer_maxlen: int = Field(default=500, ge=10, le=10000)
    otel_queue_size: int = Field(default=2048, ge=64, le=65536)
    otel_export_timeout_ms: int = Field(default=1000, ge=100, le=30000)
    fail_open_tier3: bool = Field(
        default=True,
        description="If Tier 3 OTel/Judge fails, never crash the hot-path agent step.",
    )

    # API & Security Hardening
    traceops_admin_token: Optional[SecretStr] = Field(
        default=None,
        description="Secret token required in X-TraceOps-Admin-Key on admin/span routes.",
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            "https://traceops-ai.streamlit.app",
        ],
        description="Explicit allowed CORS origins (never wildcard with credentials).",
    )
    max_request_bytes: int = Field(default=65536, ge=1024, le=1048576)
    rate_limit_rpm: int = Field(default=600, ge=10, le=100000)

    # Google AI & Optional Storage
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_judge_model: str = Field(default="gemini-3.5-flash-lite")
    gemini_baseline_model: str = Field(default="gemini-3.8-flash")
    database_url: SecretStr = Field(default=SecretStr(""))
    redis_url: Optional[SecretStr] = Field(
        default=None,
        description="Optional Redis URL for distributed multi-instance Cloud Run scaling.",
    )
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None,
        description="Optional OTLP HTTP/gRPC collector endpoint (e.g., Cloud Trace OTLP collector).",
    )
    enable_cloud_trace: bool = Field(
        default=False,
        description="Enable export to Google Cloud Trace / OTLP HTTP collector if endpoint configured.",
    )


@lru_cache(maxsize=1)
def get_settings() -> TraceOpsSettings:
    """Return cached settings singleton; call .cache_clear() in tests after env overrides."""
    return TraceOpsSettings()
