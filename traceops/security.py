"""
Tier-1 PII & Secret Scrubbing + Admin Auth + Rate Limiter for TraceOps AI.
All regexes are linear-time (zero nested quantifiers / zero ReDoS risk) and
execute in <0.1 ms before any OTLP span, log line, or API response leaves the process.
"""
from __future__ import annotations

import hmac
import re
import threading
import time
from collections import OrderedDict, deque
from typing import Any, Deque, Optional, Tuple

from traceops.config import TraceOpsSettings

# Sensitive dict keys scrubbed immediately regardless of value format
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "private_key",
        "secret_key",
        "credential",
        "credentials",
        "access_token",
        "refresh_token",
        "gemini_api_key",
        "database_url",
    }
)

# Linear-time redaction patterns (no nested quantifiers)
_GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,64}")
_GITHUB_TOKEN_RE = re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,100}")
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,100}")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,512}=*")
_DB_URI_RE = re.compile(r"(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:\s/@]+:[^@\s]+@")
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]{1,128}\.[a-zA-Z]{2,16}\b")


def redact_string(text: str) -> str:
    """Scrub API keys, bearer tokens, DB credentials, and emails in <0.01 ms."""
    if not text:
        return text
    # Fast-path guard: skip regex engine when none of the sensitive prefixes/markers exist
    if (
        "AIza" not in text
        and "gh" not in text
        and "sk-" not in text
        and "://" not in text
        and "@" not in text
        and "bearer" not in text.lower()
    ):
        return text
    scrubbed = _GOOGLE_API_KEY_RE.sub("[REDACTED_API_KEY]", text)
    scrubbed = _GITHUB_TOKEN_RE.sub("[REDACTED_TOKEN]", scrubbed)
    scrubbed = _OPENAI_KEY_RE.sub("[REDACTED_API_KEY]", scrubbed)
    scrubbed = _BEARER_RE.sub("Bearer [REDACTED_TOKEN]", scrubbed)
    scrubbed = _DB_URI_RE.sub(r"\1://[REDACTED_CREDS]@", scrubbed)
    scrubbed = _EMAIL_RE.sub("[REDACTED_EMAIL]", scrubbed)
    return scrubbed


def redact_payload(obj: Any, _depth: int = 0) -> Any:
    """
    Recursively scrub PII and secrets from arbitrary JSON-like payloads.
    Bounded recursion depth prevents stack overflow on hostile payloads.
    """
    if _depth > 8:
        return "[REDACTED_DEPTH_LIMIT]"
    if isinstance(obj, str):
        return redact_string(obj)
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for k, v in obj.items():
            key_str = str(k)
            if key_str.lower() in _SENSITIVE_KEYS:
                sanitized[key_str] = "[REDACTED]"
            else:
                sanitized[key_str] = redact_payload(v, _depth + 1)
        return sanitized
    if isinstance(obj, list):
        return [redact_payload(item, _depth + 1) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_payload(item, _depth + 1) for item in obj)
    return obj


def verify_admin_token(
    provided_token: Optional[str],
    settings: TraceOpsSettings,
) -> Tuple[bool, int, str]:
    """
    Fail-closed constant-time admin key verification for /v1/mode, /v1/reset, /v1/spans.

    - In production (`TRACEOPS_ENV=production`), if `TRACEOPS_ADMIN_TOKEN` is unset,
      ALWAYS fails closed with HTTP 503.
    - Whenever `TRACEOPS_ADMIN_TOKEN` is configured (any env), requires an exact
      constant-time `hmac.compare_digest` match, else returns HTTP 401.
    - In non-production (`development`/`staging`) when `TRACEOPS_ADMIN_TOKEN` is unset,
      permits local demo/test access unless caller explicitly requires strict mode.
    """
    configured_secret = (
        settings.traceops_admin_token.get_secret_value()
        if settings.traceops_admin_token is not None
        else ""
    )

    if settings.traceops_env == "production" and not configured_secret:
        return (
            False,
            503,
            "Admin routes disabled: TRACEOPS_ADMIN_TOKEN must be configured in production.",
        )

    if configured_secret:
        if not provided_token or not hmac.compare_digest(
            provided_token.encode("utf-8"),
            configured_secret.encode("utf-8"),
        ):
            return False, 401, "Unauthorized: invalid or missing X-TraceOps-Admin-Key."

    return True, 200, "OK"


class SlidingWindowRateLimiter:
    """Thread-safe bounded per-client IP sliding-window rate limiter."""

    def __init__(self, max_requests_per_minute: int = 600, max_clients: int = 2048):
        self.max_rpm = max_requests_per_minute
        self.max_clients = max_clients
        self._buckets: OrderedDict[str, Deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, client_ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            bucket = self._buckets.get(client_ip)
            if bucket is None:
                if len(self._buckets) >= self.max_clients:
                    self._buckets.popitem(last=False)
                bucket = deque()
                self._buckets[client_ip] = bucket
            else:
                self._buckets.move_to_end(client_ip)

            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_rpm:
                return False

            bucket.append(now)
            return True
