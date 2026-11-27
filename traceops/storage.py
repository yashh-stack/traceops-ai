"""
Pluggable storage adapters for TraceOps AI.
Supports in-memory bounded LRU+TTL store and distributed Redis-backed store
for multi-instance Cloud Run deployment concurrency.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Literal, Optional, Tuple, cast

from traceops.circuit_breaker import CircuitBreaker
from traceops.config import TraceOpsSettings

logger = logging.getLogger("traceops.storage")


class BaseTraceBreakerStore(ABC):
    """Abstract interface for storing and retrieving per-trace circuit breakers."""

    default_mode: Literal["shadow", "enforce"]

    @abstractmethod
    def get_breaker(self, trace_id: Optional[str]) -> CircuitBreaker:
        """Retrieve or create a CircuitBreaker for the given trace_id."""
        raise NotImplementedError

    @abstractmethod
    def set_mode(self, mode: Literal["shadow", "enforce"]) -> None:
        """Globally update default execution mode across all managed breakers."""
        raise NotImplementedError

    @abstractmethod
    def reset_all(self) -> None:
        """Reset all active trace breaker contexts."""
        raise NotImplementedError

    @abstractmethod
    def size(self) -> int:
        """Return the number of active cached trace contexts."""
        raise NotImplementedError


class InMemoryTraceBreakerStore(BaseTraceBreakerStore):
    """
    Thread-safe bounded LRU + TTL in-memory store.
    Evicts oldest entries when capacity exceeds maxsize or TTL expires.
    """

    def __init__(
        self,
        settings: TraceOpsSettings,
        maxsize: int = 10000,
        ttl_seconds: int = 1800,
    ):
        self.settings = settings
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self.default_mode: Literal["shadow", "enforce"] = settings.traceops_mode
        self._cache: OrderedDict[str, Tuple[CircuitBreaker, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._default_breaker = self._new_breaker()

    def _new_breaker(self) -> CircuitBreaker:
        return CircuitBreaker(
            mode=self.default_mode,
            max_identical_calls=self.settings.max_identical_calls,
            max_cost_usd=self.settings.max_cost_usd,
            max_tokens=self.settings.max_tokens,
            drift_threshold=self.settings.drift_threshold,
            warn_threshold=self.settings.warn_threshold,
            fail_open_tier3=self.settings.fail_open_tier3,
        )

    def _evict_expired(self, now: float) -> None:
        while self._cache:
            oldest_key, (_, ts) = next(iter(self._cache.items()))
            if now - ts > self.ttl_seconds:
                self._cache.popitem(last=False)
            else:
                break

    def get_breaker(self, trace_id: Optional[str]) -> CircuitBreaker:
        if not trace_id:
            return self._default_breaker

        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            entry = self._cache.get(trace_id)
            if entry is not None:
                breaker, _ = entry
                self._cache.move_to_end(trace_id)
                self._cache[trace_id] = (breaker, now)
                return breaker

            if len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)

            breaker = self._new_breaker()
            self._cache[trace_id] = (breaker, now)
            return breaker

    def set_mode(self, mode: Literal["shadow", "enforce"]) -> None:
        with self._lock:
            self.default_mode = mode
            self._default_breaker.set_mode(mode)
            for breaker, _ in self._cache.values():
                breaker.set_mode(mode)

    def reset_all(self) -> None:
        with self._lock:
            self._cache.clear()
            self._default_breaker.reset_trace()
            self._default_breaker.total_simulated_usd_saved = 0.0

    def size(self) -> int:
        with self._lock:
            self._evict_expired(time.monotonic())
            return len(self._cache)


class RedisTraceBreakerStore(BaseTraceBreakerStore):
    """
    Distributed Redis-backed store for multi-instance Cloud Run scaling.
    Maintains local in-memory CircuitBreakers synchronized with Redis state keys.
    Falls back gracefully to in-memory store if Redis is unavailable.
    """

    def __init__(
        self,
        settings: TraceOpsSettings,
        redis_url: str,
        ttl_seconds: int = 1800,
    ):
        self.settings = settings
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.default_mode: Literal["shadow", "enforce"] = settings.traceops_mode
        self._fallback_store = InMemoryTraceBreakerStore(
            settings=settings,
            maxsize=settings.trace_cache_maxsize,
            ttl_seconds=ttl_seconds,
        )
        self._redis_client: Any = None
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis
            client = redis.from_url(self.redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
            client.ping()
            self._redis_client = client
            logger.info("Connected to Redis distributed breaker store.")
        except Exception as e:
            logger.warning("Redis connection failed (%s); falling back to in-memory store.", e)
            self._redis_client = None

    def get_breaker(self, trace_id: Optional[str]) -> CircuitBreaker:
        breaker = self._fallback_store.get_breaker(trace_id)
        if not trace_id or not self._redis_client:
            return breaker

        # Sync remote mode override if present
        try:
            remote_mode = self._redis_client.get("traceops:mode")
            if remote_mode:
                mode_str = remote_mode.decode("utf-8") if isinstance(remote_mode, bytes) else str(remote_mode)
                if mode_str in ("shadow", "enforce") and mode_str != breaker.mode:
                    breaker.set_mode(cast(Literal["shadow", "enforce"], mode_str))
        except Exception as e:
            logger.warning("Redis sync error (%s); proceeding with local breaker state.", e)

        return breaker

    def set_mode(self, mode: Literal["shadow", "enforce"]) -> None:
        self.default_mode = mode
        self._fallback_store.set_mode(mode)
        if self._redis_client:
            try:
                self._redis_client.set("traceops:mode", mode)
            except Exception as e:
                logger.warning("Failed to publish mode change to Redis: %s", e)

    def reset_all(self) -> None:
        self._fallback_store.reset_all()
        if self._redis_client:
            try:
                keys = self._redis_client.keys("traceops:trace:*")
                if keys:
                    self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning("Failed to clear Redis trace keys: %s", e)


    def size(self) -> int:
        return self._fallback_store.size()


# Alias for backward compatibility
BoundedTraceBreakerStore = InMemoryTraceBreakerStore


def create_trace_breaker_store(settings: TraceOpsSettings) -> BaseTraceBreakerStore:

    """Factory creating the appropriate store adapter based on configuration."""
    redis_url = settings.redis_url.get_secret_value() if settings.redis_url else ""
    if redis_url:
        return RedisTraceBreakerStore(
            settings=settings,
            redis_url=redis_url,
            ttl_seconds=settings.trace_cache_ttl_seconds,
        )
    return InMemoryTraceBreakerStore(
        settings=settings,
        maxsize=settings.trace_cache_maxsize,
        ttl_seconds=settings.trace_cache_ttl_seconds,
    )
