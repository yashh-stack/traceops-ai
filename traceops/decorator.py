"""
Drop-in Python Decorator for TraceOps AI.
Enables instant protection of agent tool functions or step runners with:
@traceops.guard(mode="enforce", max_cost_usd=0.50)
"""
from __future__ import annotations
import functools
import inspect
from typing import Any, Callable, Dict, Literal, Optional, Set, Type
from pydantic import BaseModel

from traceops.circuit_breaker import CircuitBreaker

def guard(
    mode: Literal["shadow", "enforce"] = "enforce",
    max_identical_calls: int = 3,
    max_cost_usd: float = 0.50,
    max_tokens: int = 25000,
    drift_threshold: float = 0.55,
    scenario: str = "default",
    allowed_tools: Optional[Set[str]] = None,
    tool_schemas: Optional[Dict[str, Type[BaseModel]]] = None,
    step_cost_usd: float = 0.01,
    step_tokens: int = 100
) -> Callable:
    """
    Decorator for tool functions or agent dispatchers.
    Evaluates each invocation through TraceOps AI's synchronous hot-path guards (<15 ms).
    """
    breaker = CircuitBreaker(
        mode=mode,
        max_identical_calls=max_identical_calls,
        max_cost_usd=max_cost_usd,
        max_tokens=max_tokens,
        drift_threshold=drift_threshold,
        allowed_tools=allowed_tools,
        tool_schemas=tool_schemas
    )

    def decorator(fn: Callable) -> Callable:
        tool_name = fn.__name__

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Map positional and keyword arguments
            sig = inspect.signature(fn)
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            arg_dict = dict(bound.arguments)

            # Evaluate step on hot path
            breaker.evaluate_step(
                tool_name=tool_name,
                arguments=arg_dict,
                step_cost_usd=step_cost_usd,
                step_tokens=step_tokens,
                step_context=str(arg_dict),
                scenario=scenario
            )

            # If not halted in enforce mode, execute target function
            return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs) -> Any:
            sig = inspect.signature(fn)
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            arg_dict = dict(bound.arguments)

            breaker.evaluate_step(
                tool_name=tool_name,
                arguments=arg_dict,
                step_cost_usd=step_cost_usd,
                step_tokens=step_tokens,
                step_context=str(arg_dict),
                scenario=scenario
            )

            return await fn(*args, **kwargs)

        # Attach underlying breaker for testing/configuration inspection
        target_wrapper = async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper
        target_wrapper.breaker = breaker  # type: ignore
        return target_wrapper

    return decorator
