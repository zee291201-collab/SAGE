"""SAGE function router.

Responsibility:
    Decide WHICH capability should handle an interpreted request.
    It does not execute that capability and never calls an LLM/web service.
"""

from __future__ import annotations

from dataclasses import dataclass
from input_interpreter import InterpretedRequest

@dataclass(frozen=True)
class FunctionDecision:
    name: str
    args: dict
    confidence: float
    deterministic: bool
    requires_web: bool = False
    requires_local_knowledge: bool = False
    requires_ai: bool = False

def route_function(request: InterpretedRequest) -> FunctionDecision:
    intent = request.intent

    mapping = {
        "command": ("command", True, False, False),
        "casual": ("casual_response", True, False, False),
        "history": ("history_lookup", True, False, False),
        "research": ("web_research", False, True, False),
        "mathematics": ("math_engine", True, False, False),
        "data_analysis": ("analysis_engine", True, False, False),
        "conversion": ("conversion_engine", True, False, False),
        "memory_write": ("remember", True, False, False),
        "memory_delete": ("forget", True, False, False),
        "knowledge": ("local_first", False, False, True),
        "conversation": ("conversation", False, False, True),
        "empty": ("invalid_input", True, False, False),
    }

    name, deterministic, web, ai = mapping.get(
        intent, ("conversation", False, False, True)
    )

    if intent == "command":
        command = request.args.get("command")
        return FunctionDecision(
            command or "invalid_command", request.args, request.confidence,
            True
        )

    if intent == "research":
        name = "web_research_url" if "urls" in request.args else "web_research"

    return FunctionDecision(
        name=name,
        args=request.args,
        confidence=request.confidence,
        deterministic=deterministic,
        requires_web=web,
        requires_local_knowledge=request.requires_local_knowledge,
        requires_ai=ai,
    )

__all__ = ["FunctionDecision", "route_function"]
