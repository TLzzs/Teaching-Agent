import re

import sympy
from sympy.parsing.sympy_parser import parse_expr, rationalize, standard_transformations

from app.models import CheckResult, CheckStatus, Question

# Expressions come from the model, and parse_expr evaluates them, so only plain arithmetic is
# accepted. Powers are excluded so that inputs like 9**9**9 cannot stall the server.
_ALLOWED = re.compile(r"[0-9.+\-*/()\s]+")
_MAX_LENGTH = 200
_TRANSFORMATIONS = (*standard_transformations, rationalize)


class UnsafeExpression(ValueError):
    pass


def evaluate(expression: str) -> sympy.Expr:
    text = expression.strip()
    if not text or len(text) > _MAX_LENGTH or not _ALLOWED.fullmatch(text) or "**" in text:
        raise UnsafeExpression(f"Not a plain arithmetic expression: {expression!r}")
    try:
        value = parse_expr(text, transformations=_TRANSFORMATIONS, evaluate=True)
    except (SyntaxError, TypeError, ZeroDivisionError, sympy.SympifyError) as exc:
        raise UnsafeExpression(f"Cannot evaluate {expression!r}: {exc}") from exc
    if not value.is_number or value.has(sympy.zoo, sympy.nan):
        raise UnsafeExpression(f"Expression {expression!r} does not evaluate to a number")
    return value


def format_number(value: sympy.Expr) -> str:
    rational = sympy.nsimplify(value)
    if rational.is_Integer:
        return str(rational)
    if rational.is_Rational:
        decimal = sympy.Float(rational, 10)
        if (rational * 1000).is_Integer:
            return f"{rational} ({float(decimal):g})"
        return str(rational)
    return str(sympy.N(value, 8))


def check_question(question: Question) -> CheckResult:
    if question.check is None:
        return CheckResult(status=CheckStatus.NOT_CHECKABLE, message="No check expression")
    try:
        computed = evaluate(question.check.expression)
        expected = evaluate(question.check.expected)
    except UnsafeExpression as exc:
        return CheckResult(status=CheckStatus.INVALID, message=str(exc))

    computed_text = format_number(computed)
    if sympy.simplify(computed - expected) == 0:
        return CheckResult(status=CheckStatus.VERIFIED, computed=computed_text)
    return CheckResult(
        status=CheckStatus.MISMATCH,
        computed=computed_text,
        message=f"{question.check.expression} = {computed_text}, "
        f"but the stated answer is {question.check.expected}",
    )
