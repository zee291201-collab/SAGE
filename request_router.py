"""Compatibility facade for the split SAGE router.

Existing sage.py code can continue importing:
    from request_router import classify, execute

New code can additionally use:
    from request_router import route

The facade contains no routing rules of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from input_interpreter import interpret, InterpretedRequest
from function_router import route_function, FunctionDecision
from model_router import select_model, ModelDecision
from executor import execute_function

@dataclass
class Request:
    raw: str
    kind: str
    confidence: float
    handler: str
    args: dict[str, Any] = field(default_factory=dict)
    requires_ai: bool = False
    requires_web: bool = False
    requires_local_knowledge: bool = False
    complexity: str = "simple"
    context_messages: int = 4
    use_thinking: bool = False
    model: str | None = None
    model_tier: str = "none"

@dataclass
class ActionResult:
    ok: bool
    kind: str
    value: Any = None
    text: str = ""
    error: str | None = None

def _build(raw: str):
    parsed = interpret(raw)
    fn = route_function(parsed)
    mdl = select_model(parsed, fn)
    req = Request(
        raw=raw,
        kind=parsed.intent,
        confidence=parsed.confidence,
        handler=fn.name,
        args=fn.args,
        requires_ai=mdl.use_model,
        requires_web=fn.requires_web,
        requires_local_knowledge=fn.requires_local_knowledge,
        complexity=parsed.complexity,
        context_messages=mdl.context_messages,
        use_thinking=mdl.use_thinking,
        model=mdl.model,
        model_tier=mdl.tier,
    )
    return req, parsed, fn, mdl

def classify(text: str) -> Request:
    return _build(text)[0]

def route(text: str):
    req, parsed, fn, mdl = _build(text)
    return {
        "request": req,
        "interpreted": parsed,
        "function": fn,
        "model": mdl,
    }

def execute(request: Request, tools: dict | None = None) -> ActionResult | None:
    # Reconstruct the interpretation so the executor receives the same
    # structured request contract. This remains compatible with old sage.py.
    parsed = interpret(request.raw)
    fn = route_function(parsed)
    result = execute_function(parsed, fn, tools)
    if result is None:
        return None
    return ActionResult(result.ok, result.kind, result.value, result.text, result.error)

def parse_command(text: str):
    parsed = interpret(text)
    return parsed if parsed.intent == "command" else None

# Backward-compatible imports for code that used these symbols directly.
from deterministic_tools import safe_calculate, deterministic_math

__all__ = [
    "Request", "ActionResult", "classify", "execute", "route",
    "parse_command", "safe_calculate", "deterministic_math"
]
