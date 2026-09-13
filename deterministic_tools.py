"""Deterministic execution library extracted from the original SAGE router.

This contains the actual local calculations. Routing modules only decide
whether these functions should be used.
"""

from __future__ import annotations
import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Any, Optional
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    kind: str
    value: Any = None
    text: str = ""
    error: Optional[str] = None


try:
    from math_engine import solve_math
except ImportError:
    solve_math = None


# Safe arithmetic
# Safe arithmetic

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _finite(value: Any) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite number.")
    return value


def safe_calculate(expression: str) -> float:
    """Evaluate a restricted arithmetic expression without eval()."""
    tree = ast.parse(expression.replace("^", "**"), mode="eval")

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return _finite(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _finite(_UNARY[type(node.op)](walk(node.operand)))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise ValueError("Division by zero.")
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent too large.")
            try:
                return _finite(_BINARY[type(node.op)](left, right))
            except (OverflowError, ZeroDivisionError):
                raise ValueError("Invalid arithmetic operation.") from None
        raise ValueError("Unsupported arithmetic expression.")

    return walk(tree)


def _display(value: Any) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.12g}"
    return str(value)



# Advanced deterministic math / physics

MATH_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": lambda x: math.sin(math.radians(x)),   # degrees by default
    "cos": lambda x: math.cos(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "asin": lambda x: math.degrees(math.asin(x)),
    "acos": lambda x: math.degrees(math.acos(x)),
    "atan": lambda x: math.degrees(math.atan(x)),
    "ln": math.log,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
}

MATH_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

# Named deterministic formulas. Inputs are supplied as key=value pairs,
# e.g. "force m=10 a=5" or "kinetic energy m=2 v=20".
PHYSICS_FORMULAS = {
    "force": (("m", "a"), lambda m, a: m * a, "N"),
    "newtons second law": (("m", "a"), lambda m, a: m * a, "N"),
    "momentum": (("m", "v"), lambda m, v: m * v, "kg·m/s"),
    "kinetic energy": (("m", "v"), lambda m, v: 0.5 * m * v * v, "J"),
    "potential energy": (("m", "g", "h"), lambda m, g, h: m * g * h, "J"),
    "gravitational potential energy": (("m", "g", "h"), lambda m, g, h: m * g * h, "J"),
    "work": (("f", "d"), lambda f, d: f * d, "J"),
    "power": (("w", "t"), lambda w, t: w / t, "W"),
    "electrical power": (("v", "i"), lambda v, i: v * i, "W"),
    "ohms law": (("i", "r"), lambda i, r: i * r, "V"),
    "voltage": (("i", "r"), lambda i, r: i * r, "V"),
    "current": (("v", "r"), lambda v, r: v / r, "A"),
    "resistance": (("v", "i"), lambda v, i: v / i, "Ω"),
    "charge": (("i", "t"), lambda i, t: i * t, "C"),
    "coulomb force": (("k", "q1", "q2", "r"), lambda k, q1, q2, r: k * q1 * q2 / (r * r), "N"),
    "gravitational force": (("gconst", "m1", "m2", "r"), lambda gconst, m1, m2, r: gconst * m1 * m2 / (r * r), "N"),
    "density": (("m", "v"), lambda m, v: m / v, "kg/m³"),
    "pressure": (("f", "a"), lambda f, a: f / a, "Pa"),
    "wave speed": (("f", "wavelength"), lambda f, wavelength: f * wavelength, "m/s"),
    "frequency": (("v", "wavelength"), lambda v, wavelength: v / wavelength, "Hz"),
    "period": (("f",), lambda f: 1 / f, "s"),
    "angular velocity": (("theta", "t"), lambda theta, t: theta / t, "rad/s"),
    "centripetal force": (("m", "v", "r"), lambda m, v, r: m * v * v / r, "N"),
    "centripetal acceleration": (("v", "r"), lambda v, r: v * v / r, "m/s²"),
    "moment of inertia point mass": (("m", "r"), lambda m, r: m * r * r, "kg·m²"),
    "escape velocity": (("gconst", "m", "r"), lambda gconst, m, r: math.sqrt(2 * gconst * m / r), "m/s"),
    "mass energy": (("m", "c"), lambda m, c: m * c * c, "J"),
}

PHYSICS_ALIASES = {
    "ke": "kinetic energy",
    "kinetic": "kinetic energy",
    "pe": "potential energy",
    "potential": "potential energy",
    "newton 2": "force",
    "newton's second law": "force",
    "ohm": "ohms law",
    "coulomb": "coulomb force",
    "gravity force": "gravitational force",
    "centripetal": "centripetal force",
    "e=mc2": "mass energy",
    "e=mc^2": "mass energy",
}

def _parse_named_values(text: str) -> dict[str, float]:
    """Parse key=value numeric inputs, including scientific notation."""
    out = {}
    pattern = re.compile(
        rf"\b([a-zA-Z][a-zA-Z0-9_]*)\s*=\s*({NUMBER})"
    )
    for key, value in pattern.findall(text):
        out[key.lower()] = float(value)
    return out


def _normalize_formula_name(text: str) -> str:
    s = re.sub(r"\s+", " ", text.lower().strip())
    s = re.sub(r"^(calculate|compute|find|solve)\s+", "", s)
    s = re.sub(r"\bfor\b.*$", "", s).strip()
    return PHYSICS_ALIASES.get(s, s)


def deterministic_math(text: str) -> Optional[ActionResult]:
    """
    Try an advanced deterministic math/physics request.

    Uses the SymPy-backed math engine first for advanced mathematics,
    then falls back to the existing deterministic physics/math handlers.

    Returns None when the request is not confidently recognized,
    allowing ambiguous natural-language questions to reach Qwen.
    """
    raw = text.strip()
    normalized = re.sub(r"\s+", " ", raw.lower())

    # --------------------------------------------------------------
    # SymPy-backed advanced mathematics
    # --------------------------------------------------------------
    # Normalize common natural-language mathematical expressions
    # before passing them to math_engine.py.

    math_input = re.sub(r"^(?:what is|what\'s|calculate|compute|find|evaluate)\s+", "", normalized)
    math_input = math_input.rstrip("?").strip()

    # Common natural-language square-root forms:
    # "square root of 169" / "sq root of 169" / "sqrt of 169"
    # / "square root 169" -> "sqrt(169)"
    math_input = re.sub(
        r"\b(?:square|sq)\s+root(?:\s+of)?\s+(.+)$",
        r"sqrt(\1)",
        math_input,
    )
    math_input = re.sub(
        r"\bsqrt\s+of\s+(.+)$",
        r"sqrt(\1)",
        math_input,
    )

    # Explicit base-10 logarithm: "log10 of 50" -> "log(50, 10)"
    math_input = re.sub(
        r"\blog10\s+of\s+(.+)$",
        r"log10(\1)",
        math_input,
    )

    # "log of 500" / "logarithm of 500" / "natural log of 500"
    # → "log(500)" (natural logarithm)
    math_input = re.sub(
        r"\b(?:natural\s+)?log(?:arithm)?\s+of\s+",
        "log(",
        math_input,
    )

    # "ln 500" → "log(500)"
    math_input = re.sub(
        r"\bln\s+([0-9]+(?:\.[0-9]+)?)\b",
        r"log(\1)",
        math_input,
    )

    # "log 500" → "log(500)"
    math_input = re.sub(
        r"\blog\s+([0-9]+(?:\.[0-9]+)?)\b",
        r"log(\1)",
        math_input,
    )

    # Close parentheses introduced by the natural-language
    # conversions above.
    if (
        math_input.startswith("log(")
        and math_input.count("(") > math_input.count(")")
    ):
        math_input += ")"

    if solve_math is not None:
        try:
            result = solve_math(math_input)

            if result is not None:
                return ActionResult(
                    True,
                    "math",
                    result,
                    str(result),
                )

        except Exception:
            # SymPy should never prevent the existing deterministic
            # math/physics handlers from working.
            pass

    # --------------------------------------------------------------
    # Explicit physics formula syntax
    # Example:
    #     force m=10 a=5
    # --------------------------------------------------------------

    values = _parse_named_values(raw)

    if values:
        formula_text = re.sub(
            r"\b[a-zA-Z][a-zA-Z0-9_]*\s*=\s*[-+0-9.eE]+\b",
            "",
            normalized,
        )

        formula_text = re.sub(
            r"[^a-z0-9²^ ='-]",
            " ",
            formula_text,
        )

        formula_text = re.sub(
            r"\s+",
            " ",
            formula_text,
        ).strip()

        formula_name = _normalize_formula_name(formula_text)

        # Common alternate key names.
        aliases = {
            "mass": "m",
            "acceleration": "a",
            "velocity": "v",
            "speed": "v",
            "time": "t",
            "distance": "d",
            "force": "f",
            "area": "a",
            "radius": "r",
            "wavelength": "wavelength",
            "frequency": "f",
            "voltage": "v",
            "current": "i",
            "resistance": "r",
            "height": "h",
            "work": "w",
            "c": "c",
            "g": "g",
            "gconst": "gconst",
            "charge1": "q1",
            "charge2": "q2",
        }

        for old, new in aliases.items():
            if old in values and new not in values:
                values[new] = values[old]

        if formula_name in PHYSICS_FORMULAS:
            required, fn, unit = PHYSICS_FORMULAS[formula_name]

            if all(key in values for key in required):
                try:
                    result = _finite(
                        fn(*(values[key] for key in required))
                    )

                    return ActionResult(
                        True,
                        "physics",
                        result,
                        f"{_display(result)} {unit}",
                    )

                except (
                    ValueError,
                    ZeroDivisionError,
                    OverflowError,
                ):
                    return ActionResult(
                        False,
                        "physics",
                        error="Invalid formula inputs.",
                    )

    # --------------------------------------------------------------
    # Compact kinematics equation
    #
    # s = ut + 1/2*a*t^2
    # --------------------------------------------------------------

    m = re.fullmatch(
        rf"\s*s\s*=\s*({NUMBER})\s*\*\s*({NUMBER})"
        rf"\s*\+\s*0?\.?5\s*\*\s*({NUMBER})"
        rf"\s*\*\s*({NUMBER})\s*\^?\s*2\s*",
        normalized,
    )

    if m:
        u = float(m.group(1))
        t = float(m.group(2))
        a = float(m.group(3))
        t2 = float(m.group(4))

        if t == t2:
            result = u * t + 0.5 * a * t * t

            return ActionResult(
                True,
                "physics",
                result,
                f"{_display(result)} m",
            )

    # --------------------------------------------------------------
    # Legacy deterministic math evaluator
    #
    # Handles simple expressions such as:
    #     sqrt(144)
    #     sin(30)
    #     pi * 2
    #     2^8
    #
    # SymPy was already given first opportunity above.
    # --------------------------------------------------------------

    expr = math_input.replace("^", "**")

    if re.fullmatch(
        r"[0-9eE.\s+\-*/%(),a-z]+",
        expr,
    ):
        try:
            tree = ast.parse(expr, mode="eval")

            def walk_math(node: ast.AST) -> float:
                if isinstance(node, ast.Expression):
                    return walk_math(node.body)

                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, (int, float))
                ):
                    return _finite(node.value)

                if (
                    isinstance(node, ast.Name)
                    and node.id in MATH_CONSTANTS
                ):
                    return MATH_CONSTANTS[node.id]

                if (
                    isinstance(node, ast.UnaryOp)
                    and type(node.op) in _UNARY
                ):
                    return _finite(
                        _UNARY[type(node.op)](
                            walk_math(node.operand)
                        )
                    )

                if (
                    isinstance(node, ast.BinOp)
                    and type(node.op) in _BINARY
                ):
                    left = walk_math(node.left)
                    right = walk_math(node.right)

                    if (
                        isinstance(
                            node.op,
                            (ast.Div, ast.FloorDiv, ast.Mod),
                        )
                        and right == 0
                    ):
                        raise ValueError("Division by zero.")

                    if (
                        isinstance(node.op, ast.Pow)
                        and abs(right) > 1000
                    ):
                        raise ValueError("Exponent too large.")

                    return _finite(
                        _BINARY[type(node.op)](
                            left,
                            right,
                        )
                    )

                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                ):
                    fn = MATH_FUNCTIONS.get(node.func.id)

                    if (
                        fn is None
                        or len(node.args) != 1
                        or node.keywords
                    ):
                        raise ValueError(
                            "Unsupported math function."
                        )

                    return _finite(
                        fn(walk_math(node.args[0]))
                    )

                raise ValueError("Unsupported expression.")

            if (
                any(name in expr for name in MATH_FUNCTIONS)
                or any(c in expr for c in MATH_CONSTANTS)
            ):
                value = walk_math(tree)

                return ActionResult(
                    True,
                    "math",
                    value,
                    _display(value),
                )

        except (
            ValueError,
            SyntaxError,
            TypeError,
            OverflowError,
        ):
            pass

    return None


__all__ = [
    "safe_calculate", "deterministic_math", "ActionResult",
    "PHYSICS_FORMULAS", "MATH_FUNCTIONS"
]
