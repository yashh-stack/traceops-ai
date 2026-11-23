"""
TraceOps AI: Deterministic Agent Circuit-Breaker & Runtime Evals Engine.
Package initialization and public exports.
"""
import traceops.shims  # Install runtime binary shims before importing langgraph

from traceops.circuit_breaker import CircuitBreaker, CircuitBreakerError
from traceops.decorator import guard
from traceops.guards.deterministic import DeterministicGuard, Tier1Violation
from traceops.guards.semantic_drift import SemanticDriftScorer
from traceops.otel_exporter import TraceOpsOtelEmitter

__version__ = "0.1.0"
__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "guard",
    "DeterministicGuard",
    "Tier1Violation",
    "SemanticDriftScorer",
    "TraceOpsOtelEmitter",
]
