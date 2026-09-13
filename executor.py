"""SAGE deterministic executor.

The executor is the only layer here that actually performs deterministic
operations. LLMs/web/local retrieval are deliberately outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from function_router import FunctionDecision
from deterministic_tools import ActionResult, safe_calculate, deterministic_math

def execute_function(
    request,
    decision: FunctionDecision,
    tools: dict[str, Callable[..., Any]] | None = None,
) -> ActionResult | None:
    tools = tools or {}
    name = decision.name

    if name == "casual_response":
        response = request.args["response"]
        return ActionResult(True, "casual", response, response)

    if name == "math_engine":
        result = deterministic_math(request.raw)
        if result is not None:
            return result
        return None

    if name == "invalid_input":
        return ActionResult(False, "input", error="Empty request.")

    # Commands, memory, history, analysis, conversion and other local
    # capabilities are supplied by SAGE through the tools dictionary.
    handler = tools.get(name)
    if handler is None:
        return None

    try:
        value = handler(**decision.args)
    except Exception as exc:
        return ActionResult(False, request.intent, error=str(exc))

    if isinstance(value, ActionResult):
        return value

    return ActionResult(True, request.intent, value, str(value))

__all__ = ["execute_function"]
