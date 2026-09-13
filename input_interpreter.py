"""SAGE input interpreter.

Responsibility:
    Convert raw user input into a structured intent.
    This module does NOT execute functions, access the web, call an LLM,
    or perform calculations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
URL_RE = re.compile(r'https?://[^\s<>"\']+')

CASUAL = {
    "hi": "Hello, Lunar.",
    "hello": "Hello, Lunar.",
    "hey": "Hey, Lunar.",
    "hiya": "Hello.",
    "yo": "Hey.",
    "sup": "Operational.",
    "thanks": "You're welcome.",
    "thank you": "You're welcome.",
    "thx": "You're welcome.",
    "ok": "Understood.",
    "okay": "Understood.",
    "cool": "Indeed.",
    "bye": "Bye, Lunar.",
    "goodbye": "Goodbye.",
}

RESEARCH_TERMS = (
    "research", "look up", "search online", "search the web",
    "find out", "investigate", "verify", "fact check", "check online",
    "latest", "recent", "current", "today", "news",
)

HISTORY_TERMS = (
    "what did i just ask", "what did i ask", "my previous question",
    "previous prompt", "what did we discuss", "what did you say earlier",
    "what was the last thing", "what did we talk about",
)

ANALYSIS_TERMS = (
    "average of", "mean of", "median of", "mode of", "standard deviation",
    "variance", "range of", "percentage", "percent change",
    "percentage change", "correlation", "regression",
)

CONVERSION_RE = re.compile(
    rf"{NUMBER}\s*[a-zA-Z°]+\s+(?:to|in)\s+[a-zA-Z°]+", re.I
)

MATH_WORDS = (
    "square root", "sqrt", "log", "log10", "ln", "sin", "cos", "tan",
    "arcsin", "arccos", "arctan", "differentiate", "derivative",
    "integrate", "integral", "limit", "solve", "simplify", "factor",
    "expand", "matrix", "determinant", "inverse", "eigenvalue",
    "equation", "newton", "kinetic energy", "potential energy",
    "momentum", "centripetal", "ohm", "coulomb", "density", "pressure",
    "wave speed", "frequency", "period", "power", "voltage", "current",
    "resistance", "charge", "force", "work", "mass energy",
)

COMPLEX_MARKERS = (
    "design ", "architect", "debug ", "troubleshoot", "optimize",
    "compare", "analyze", "calculate how", "derive ", "why does",
    "plan ", "build ", "implement", "write a program", "code ",
)

@dataclass
class InterpretedRequest:
    raw: str
    normalized: str
    intent: str
    confidence: float
    args: dict[str, Any] = field(default_factory=dict)
    complexity: str = "simple"
    context_messages: int = 4
    explicit_web: bool = False
    requires_local_knowledge: bool = False
    requires_ai: bool = False

def _command_intent(raw: str, normalized: str) -> Optional[InterpretedRequest]:
    m = re.match(r"^log\s+chat\s*:\s*(.+)$", raw, re.I)
    if m:
        name = m.group(1).strip()
        if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"\'":
            name = name[1:-1].strip()
        return InterpretedRequest(raw, normalized, "command", 1.0,
                                  {"command": "log_chat", "name": name})

    m = re.match(r"^access\s+chat(?:\s*:\s*|\s+)(.+)$", raw, re.I)
    if m:
        name = m.group(1).strip()
        if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"\'":
            name = name[1:-1].strip()
        return InterpretedRequest(raw, normalized, "command", 1.0,
                                  {"command": "access_chat", "name": name})

    if normalized in {"/quit", "/exit", "shutdown", "shut down", "power down", "go offline"}:
        return InterpretedRequest(raw, normalized, "command", 1.0,
                                  {"command": "shutdown"})

    if normalized in {"/clear", "clear chat", "clear the chat",
                      "clear conversation", "clear the conversation"}:
        return InterpretedRequest(raw, normalized, "command", 1.0,
                                  {"command": "clear_chat"})

    return None

def _looks_like_math(s: str) -> bool:
    stripped = re.sub(r"^(?:what is|what's|calculate|compute|find|evaluate)\s+", "", s)
    if re.fullmatch(r"[0-9eE.\s+\-*/%()^]+", stripped.rstrip("?").strip()):
        return bool(re.search(r"[+\-*/%^]", stripped))
    return any(term in s for term in MATH_WORDS)

def interpret(text: str) -> InterpretedRequest:
    raw = text.strip()
    normalized = re.sub(r"\s+", " ", raw.lower())

    if not raw:
        return InterpretedRequest(raw, normalized, "empty", 1.0)

    command = _command_intent(raw, normalized)
    if command:
        return command

    if normalized in CASUAL:
        return InterpretedRequest(
            raw, normalized, "casual", 1.0,
            {"response": CASUAL[normalized]}
        )

    if any(term in normalized for term in HISTORY_TERMS):
        return InterpretedRequest(raw, normalized, "history", 0.99,
                                  context_messages=0)

    urls = URL_RE.findall(raw)
    if urls:
        return InterpretedRequest(
            raw, normalized, "research", 1.0,
            {"urls": urls}, explicit_web=True,
            complexity="complex", context_messages=4
        )

    if any(term in normalized for term in RESEARCH_TERMS):
        return InterpretedRequest(
            raw, normalized, "research", 0.98,
            explicit_web=True, complexity="complex", context_messages=4
        )

    if re.match(r"^(remember|save|store|note|keep in mind)\b", normalized):
        return InterpretedRequest(raw, normalized, "memory_write", 1.0)

    if re.match(r"^(forget|delete|remove)\b", normalized):
        return InterpretedRequest(raw, normalized, "memory_delete", 1.0)

    if any(term in normalized for term in ANALYSIS_TERMS):
        return InterpretedRequest(raw, normalized, "data_analysis", 0.98,
                                  context_messages=0)

    if CONVERSION_RE.search(normalized):
        return InterpretedRequest(raw, normalized, "conversion", 0.95,
                                  context_messages=0)

    if _looks_like_math(normalized):
        return InterpretedRequest(raw, normalized, "mathematics", 0.97,
                                  context_messages=0)

    if normalized.endswith("?") or normalized.startswith((
        "what ", "why ", "how ", "when ", "where ", "who ", "which ",
        "can ", "could ", "does ", "do ", "is ", "are ", "will ",
        "would ", "should ",
    )):
        return InterpretedRequest(
            raw, normalized, "knowledge", 0.80,
            complexity="simple", context_messages=4,
            requires_local_knowledge=True
        )

    is_complex = (
        len(normalized) > 180
        or any(marker in normalized for marker in COMPLEX_MARKERS)
    )

    return InterpretedRequest(
        raw, normalized, "conversation", 0.60,
        complexity="complex" if is_complex else "simple",
        context_messages=6 if is_complex else 4,
        requires_ai=True
    )

__all__ = ["InterpretedRequest", "interpret", "CASUAL"]
