"""
Deterministic Tier-1 Guards for TraceOps AI Circuit Breaker.
Guarantees sub-millisecond execution (<1 ms) for:
1. Exact duplicate tool-call hash detector (max_identical_calls=3).
2. Per-trace token & USD budget ceiling (max_cost_usd, max_tokens).
3. Least-privilege tool allowlist + Pydantic schema validation.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Type
from pydantic import BaseModel, ValidationError

class Tier1Violation(Exception):
    """Raised when a Tier 1 deterministic check fails."""
    def __init__(self, rule: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.rule = rule
        self.message = message
        self.details = details or {}

class DeterministicGuard:
    """
    Tier-1 Microsecond Latency Policy Guard.
    Zero network calls. Pure in-memory hashing, sets, and schema validation.
    """
    def __init__(
        self,
        max_identical_calls: int = 3,
        max_cost_usd: float = 0.50,
        max_tokens: int = 25000,
        allowed_tools: Optional[Set[str]] = None,
        tool_schemas: Optional[Dict[str, Type[BaseModel]]] = None,
    ):
        self.max_identical_calls = max_identical_calls
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        # Default benign allowlist if not supplied
        self.allowed_tools = allowed_tools if allowed_tools is not None else {
            "query_gke_telemetry",
            "search_knowledge_base",
            "fetch_pod_logs",
            "get_service_metrics",
            "run_canary_test",
            "refund_user"
        }
        self.tool_schemas = tool_schemas or {}
        # Trace tracking state: call_hash -> count
        self.call_history: Dict[str, int] = {}
        self.cumulative_cost_usd: float = 0.0
        self.cumulative_tokens: int = 0

    def reset(self) -> None:
        """Reset state for a fresh trace."""
        self.call_history.clear()
        self.cumulative_cost_usd = 0.0
        self.cumulative_tokens = 0

    def hash_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate deterministic MD5 hash of tool name and canonical JSON arguments."""
        canonical_args = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        content = f"{tool_name}:{canonical_args}".encode("utf-8")
        return hashlib.md5(content).hexdigest()

    def evaluate_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        step_cost_usd: float = 0.0,
        step_tokens: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluate tool call against Tier-1 rules in <1 ms.
        Returns evaluation metadata or raises Tier1Violation.
        """
        # Rule 1: Tool Allowlist Check
        if self.allowed_tools and tool_name not in self.allowed_tools:
            raise Tier1Violation(
                rule="unauthorized_tool",
                message=f"Tool '{tool_name}' is not in least-privilege allowlist.",
                details={"tool_name": tool_name, "allowed_tools": sorted(list(self.allowed_tools))}
            )

        # Rule 2: Pydantic Schema Validation (if registered)
        if tool_name in self.tool_schemas:
            schema_cls = self.tool_schemas[tool_name]
            try:
                schema_cls.model_validate(arguments)
            except ValidationError as e:
                raise Tier1Violation(
                    rule="schema_validation_error",
                    message=f"Arguments failed schema validation for tool '{tool_name}': {e}",
                    details={"tool_name": tool_name, "validation_errors": e.errors()}
                )

        # Rule 3: Exact Duplicate Call Loop Detection
        call_hash = self.hash_tool_call(tool_name, arguments)
        current_count = self.call_history.get(call_hash, 0) + 1
        self.call_history[call_hash] = current_count

        if current_count >= self.max_identical_calls:
            raise Tier1Violation(
                rule="runaway_loop",
                message=f"Runaway loop detected: tool '{tool_name}' called {current_count} times with identical arguments.",
                details={
                    "tool_name": tool_name,
                    "call_hash": call_hash,
                    "identical_count": current_count,
                    "max_allowed": self.max_identical_calls
                }
            )

        # Rule 4: Hard Budget Ceiling (USD & Tokens)
        self.cumulative_cost_usd += step_cost_usd
        self.cumulative_tokens += step_tokens

        if self.cumulative_cost_usd > self.max_cost_usd:
            raise Tier1Violation(
                rule="cost_ceiling_exceeded",
                message=f"Trace cost ceiling exceeded: ${self.cumulative_cost_usd:.4f} > limit ${self.max_cost_usd:.4f}",
                details={"cumulative_cost_usd": self.cumulative_cost_usd, "limit": self.max_cost_usd}
            )

        if self.cumulative_tokens > self.max_tokens:
            raise Tier1Violation(
                rule="token_ceiling_exceeded",
                message=f"Token budget ceiling exceeded: {self.cumulative_tokens} > limit {self.max_tokens}",
                details={"cumulative_tokens": self.cumulative_tokens, "limit": self.max_tokens}
            )

        return {
            "status": "PASS",
            "call_hash": call_hash,
            "identical_count": current_count,
            "cumulative_cost_usd": round(self.cumulative_cost_usd, 6),
            "cumulative_tokens": self.cumulative_tokens
        }
