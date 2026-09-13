"""SAGE deterministic symbolic math engine powered by SymPy.

This module never calls an LLM. It is deliberately conservative about parsing
natural-language input and only passes a sanitized mathematical expression to
SymPy's parser.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
    )
    SYMPY_AVAILABLE = True
except Exception:
    sp = None
    SYMPY_AVAILABLE = False

TRANSFORMS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)

SAFE_NAMES = {
    name: getattr(sp, name)
    for name in (
        "pi", "E", "I", "oo", "sin", "cos", "tan", "asin", "acos", "atan",
        "sinh", "cosh", "tanh", "sqrt", "log", "exp", "Abs", "factorial",
        "gamma", "erf",
    )
} if SYMPY_AVAILABLE else {}

# Keep parsing bounded. SymPy is powerful enough that unrestricted expressions
# can become computationally expensive.
MAX_EXPR_CHARS = 500
MAX_MATRIX_ELEMENTS = 100


def _clean(text: str) -> str:
    text = text.strip()
    text = text.replace("−", "-").replace("×", "*").replace("÷", "/")
    text = text.replace("²", "^2").replace("³", "^3")
    text = re.sub(r"\bto the power of\b", "^", text, flags=re.I)
    return re.sub(r"\s+", " ", text)


def _symbols(expr_text: str):
    names = set(re.findall(r"\b[a-zA-Z]\w*\b", expr_text))
    reserved = set(SAFE_NAMES)
    return {n: sp.Symbol(n) for n in names if n not in reserved}


def _parse(expr_text: str):
    if not SYMPY_AVAILABLE:
        raise RuntimeError("SymPy is not installed. Run: python3 -m pip install sympy")
    expr_text = _clean(expr_text)
    if not expr_text or len(expr_text) > MAX_EXPR_CHARS:
        raise ValueError("Expression is empty or too long.")
    # Only mathematical characters, names and basic delimiters are accepted.
    if not re.fullmatch(r"[A-Za-z0-9_+\-*/^().,\[\]{}= !]+", expr_text):
        raise ValueError("Unsupported characters in mathematical expression.")
    local = dict(SAFE_NAMES)
    local.update(_symbols(expr_text))
    # parse_expr uses eval internally, so global_dict is explicitly restricted.
    global_dict = {
        "__builtins__": {},
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "Symbol": sp.Symbol,
        "Add": sp.Add,
        "Mul": sp.Mul,
        "Pow": sp.Pow,
    }
    return parse_expr(
        expr_text,
        local_dict=local,
        global_dict=global_dict,
        transformations=TRANSFORMS,
        evaluate=True,
    )


def _fmt(value) -> str:
    if not SYMPY_AVAILABLE:
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        return sp.sstr(value)
    value = sp.simplify(value)
    text = sp.sstr(value)
    if getattr(value, "is_number", False) and getattr(value, "is_real", False):
        try:
            numeric = value.evalf(12)
            if numeric != value:
                text += f"  ≈  {sp.N(numeric, 10)}"
        except Exception:
            pass
    return text


def _extract_after(text: str, patterns) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return m.group(1).strip()
    return None


def solve_math(text: str):
    """Return a deterministic result string, or None when not recognized."""
    if not SYMPY_AVAILABLE:
        return None
    raw = _clean(text)
    low = raw.lower()

    try:
        # Derivative / differentiation
        expr_text = _extract_after(low, [r"^(?:differentiate|derivative of|derive)\s+(.+)$"])
        if expr_text:
            expr = _parse(expr_text)
            var = next(iter(sorted(expr.free_symbols, key=str)), sp.Symbol("x"))
            return _fmt(sp.diff(expr, var))

        # Integral / integration
        expr_text = _extract_after(low, [r"^(?:integrate|integral of)\s+(.+)$"])
        if expr_text:
            expr = _parse(expr_text)
            var = next(iter(sorted(expr.free_symbols, key=str)), sp.Symbol("x"))
            return _fmt(sp.integrate(expr, var))

        # Limit: "limit sin(x)/x as x->0"
        m = re.match(r"^limit\s+(.+?)\s+as\s+([a-zA-Z]\w*)\s*(?:->|→|to)\s*(.+)$", low)
        if m:
            expr = _parse(m.group(1))
            var = sp.Symbol(m.group(2))
            point = _parse(m.group(3))
            return _fmt(sp.limit(expr, var, point))

        # Solve equation(s): "solve x^2+5x+6=0" or "solve x+y=5, x-y=1"
        expr_text = _extract_after(low, [r"^solve\s+(.+)$", r"^find roots of\s+(.+)$"])
        if expr_text:
            parts = [p.strip() for p in re.split(r"\s*(?:,|;|\band\b)\s*", expr_text) if p.strip()]
            equations = []
            for part in parts:
                if "=" in part:
                    left, right = part.split("=", 1)
                    equations.append(_parse(left) - _parse(right))
                else:
                    equations.append(_parse(part))
            symbols = sorted(set().union(*(e.free_symbols for e in equations)), key=str)
            result = sp.solve(equations, symbols, dict=True)
            return _fmt(result)

        # Simplify/factor/expand
        for verb, fn in (("simplify", sp.simplify), ("factor", sp.factor), ("expand", sp.expand)):
            expr_text = _extract_after(low, [rf"^{verb}\s+(.+)$"])
            if expr_text:
                return _fmt(fn(_parse(expr_text)))

        # Matrix commands: matrix [[...]] determinant/inverse/eigenvalues/etc.
        m = re.match(r"^(?:determinant|det|inverse|eigenvalues|eigenvectors|matrix\s+multiply)\s*(.*)$", low)
        if m:
            body = m.group(1).strip()
            if body.startswith("matrix "):
                body = body[7:].strip()
            # Basic safe matrix literal only.
            if not re.fullmatch(r"\s*\[\s*\[.*\]\s*(?:,\s*\[.*\]\s*)+\]\s*", body):
                raise ValueError("Use a matrix like [[1,2],[3,4]].")
            matrix = sp.Matrix(eval(body, {"__builtins__": {}}, {}))
            if matrix.rows * matrix.cols > MAX_MATRIX_ELEMENTS:
                raise ValueError("Matrix is too large.")
            command = low.split()[0]
            if command in ("determinant", "det"):
                return _fmt(matrix.det())
            if command == "inverse":
                return _fmt(matrix.inv())
            if command == "eigenvalues":
                return _fmt(matrix.eigenvals())
            if command == "eigenvectors":
                return _fmt(matrix.eigenvects())
            # matrix multiply is intentionally handled by a future structured API

        # Explicit expression evaluation / arithmetic with functions.
        if re.fullmatch(r"[A-Za-z0-9_+\-*/^()., !]+", low) and (
            re.search(r"[+\-*/^()]", low) or any(fn in low for fn in SAFE_NAMES)
        ):
            return _fmt(_parse(low))

    except Exception as exc:
        # Recognized mathematical commands should return a useful error instead
        # of silently pretending the calculation succeeded.
        if re.match(r"^(differentiate|derivative|derive|integrate|integral|limit|solve|find roots|simplify|factor|expand|determinant|det|inverse|eigenvalues|eigenvectors)\b", low):
            return f"Math error: {exc}"
        return None

    return None


__all__ = ["solve_math", "SYMPY_AVAILABLE"]
