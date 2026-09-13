"""SAGE model router.

Responsibility:
    Select whether an LLM is needed and which model tier should be used.
    It never loads or calls a model.

The policy is intentionally hardware-aware but configuration-driven.
Change MODEL_CONFIG rather than scattering model names through SAGE.
"""

from __future__ import annotations

from dataclasses import dataclass
from function_router import FunctionDecision
from input_interpreter import InterpretedRequest

MODEL_CONFIG = {
    "formatter": "qwen3:1.7b",
    "general": "qwen3:4b",
    "reasoning": "sage-qwen",
}

@dataclass(frozen=True)
class ModelDecision:
    use_model: bool
    model: str | None
    tier: str
    use_thinking: bool
    context_messages: int
    reason: str

def select_model(
    request: InterpretedRequest,
    function: FunctionDecision,
    *,
    vision_available: bool = False
) -> ModelDecision:

    # ============================================================
    # NO MODEL
    # ============================================================

    # Deterministic functions should never wait for an LLM.
    if function.deterministic:
        return ModelDecision(
            False,
            None,
            "none",
            False,
            request.context_messages,
            "deterministic capability"
        )

    # ============================================================
    # VISION
    # ============================================================

    if vision_available and request.intent == "vision":
        # Only enable this after adding a real vision model.
        return ModelDecision(
            True,
            MODEL_CONFIG["vision"],
            "vision",
            request.complexity == "complex",
            request.context_messages,
            "vision input detected"
        )

    # ============================================================
    # WEB RESEARCH → AI SYNTHESIS
    # ============================================================

    if function.requires_web:
        if request.complexity == "complex":
            return ModelDecision(
                True,
                MODEL_CONFIG["reasoning"],
                "reasoning",
                True,
                request.context_messages,
                "complex web evidence requires reasoning"
            )

        return ModelDecision(
            True,
            MODEL_CONFIG["general"],
            "general",
            False,
            request.context_messages,
            "web evidence requires language synthesis"
        )

    # ============================================================
    # LOCAL KNOWLEDGE → AI SYNTHESIS
    # ============================================================

    if request.intent == "knowledge":
        if request.complexity == "complex":
            return ModelDecision(
                True,
                MODEL_CONFIG["reasoning"],
                "reasoning",
                True,
                request.context_messages,
                "complex local-knowledge synthesis"
            )

        # Simple knowledge cleanup / summarization.
        return ModelDecision(
            True,
            MODEL_CONFIG["formatter"],
            "formatter",
            False,
            request.context_messages,
            "local knowledge requires filtering and phrasing"
        )

    # ============================================================
    # GENERAL AI
    # ============================================================

    if function.requires_ai:
        if request.complexity == "complex":
            return ModelDecision(
                True,
                MODEL_CONFIG["reasoning"],
                "reasoning",
                True,
                request.context_messages,
                "complex reasoning request"
            )

        return ModelDecision(
            True,
            MODEL_CONFIG["general"],
            "general",
            False,
            request.context_messages,
            "general AI request"
        )

    # ============================================================
    # NO AI REQUIRED
    # ============================================================

    return ModelDecision(
        False,
        None,
        "none",
        False,
        request.context_messages,
        "no model required"
    )

__all__ = ["ModelDecision", "MODEL_CONFIG", "select_model"]
"""SAGE model router.

Responsibility:
    Select whether an LLM is needed and which model tier should be used.
    It never loads or calls a model.

The policy is intentionally hardware-aware but configuration-driven.
Change MODEL_CONFIG rather than scattering model names through SAGE.
"""

from __future__ import annotations

from dataclasses import dataclass
from function_router import FunctionDecision
from input_interpreter import InterpretedRequest

MODEL_CONFIG = {
    "fast": "sage-qwen-fast",
    "reasoning": "sage-qwen",
    "vision": "sage-vision",
}

@dataclass(frozen=True)
class ModelDecision:
    use_model: bool
    model: str | None
    tier: str
    use_thinking: bool
    context_messages: int
    reason: str

def select_model(request: InterpretedRequest,
                 function: FunctionDecision,
                 *,
                 vision_available: bool = False) -> ModelDecision:

    # Safety/deterministic functions never wait for an LLM.
    if function.deterministic:
        return ModelDecision(False, None, "none", False,
                             request.context_messages, "deterministic capability")

    if function.requires_web:
        # Web retrieval happens before the language model. The model may
        # summarize/reason over retrieved evidence afterward.
        tier = "reasoning" if request.complexity == "complex" else "fast"
        return ModelDecision(
            True, MODEL_CONFIG[tier], tier,
            request.complexity == "complex",
            request.context_messages,
            "web research requires language synthesis"
        )

    if request.intent == "knowledge":
        return ModelDecision(
            True, MODEL_CONFIG["reasoning"] if request.complexity == "complex"
            else MODEL_CONFIG["fast"],
            "reasoning" if request.complexity == "complex" else "fast",
            request.complexity == "complex",
            request.context_messages,
            "local knowledge may need language synthesis"
        )

    if vision_available and request.intent == "vision":
        return ModelDecision(
            True, MODEL_CONFIG["vision"], "vision",
            request.complexity == "complex",
            request.context_messages,
            "vision input detected"
        )

    if function.requires_ai:
        tier = "reasoning" if request.complexity == "complex" else "fast"
        return ModelDecision(
            True, MODEL_CONFIG[tier], tier,
            request.complexity == "complex",
            request.context_messages,
            "conversation complexity"
        )

    return ModelDecision(False, None, "none", False,
                         request.context_messages, "no model required")

__all__ = ["ModelDecision", "MODEL_CONFIG", "select_model"]
