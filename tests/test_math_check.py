import pytest

from app.models import CheckStatus, MathCheck, Question
from app.verify.math_check import UnsafeExpression, check_question, evaluate


def make(expression: str, expected: str) -> Question:
    return Question(
        prompt="q", answer=expected, check=MathCheck(expression=expression, expected=expected)
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("3/8+1/8", "1/2"),
        ("0.1+0.2", "0.3"),
        ("25/100*80", "20"),
        ("2+3/4-5/4", "3/2"),
        ("5-(-6)", "11"),
        ("(4+7+9+8)/4", "7"),
    ],
)
def test_correct_answers_are_verified(expression, expected):
    assert check_question(make(expression, expected)).status == CheckStatus.VERIFIED


def test_wrong_answer_is_reported_with_computed_value():
    result = check_question(make("7*8", "54"))
    assert result.status == CheckStatus.MISMATCH
    assert result.computed == "56"


@pytest.mark.parametrize(
    "expression",
    ["__import__('os')", "9**9**9", "x+1", "1/0", "", "1" * 300, "2^3"],
)
def test_unsafe_or_invalid_expressions_are_rejected(expression):
    with pytest.raises(UnsafeExpression):
        evaluate(expression)
    assert check_question(make(expression, "1")).status == CheckStatus.INVALID


def test_question_without_check_is_flagged_for_teacher():
    question = Question(prompt="Explain why", answer="Because ...")
    assert check_question(question).status == CheckStatus.NOT_CHECKABLE
