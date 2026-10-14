import json

import pytest

from app.data_loader import load_curriculum, load_template
from app.llm.mock import MockProvider
from app.models import CheckStatus, LessonRequest
from app.workflow.engine import GenerationError, LessonGenerator, build_context
from app.workflow.prompt import build_section_prompt
from tests.conftest import ScriptedProvider, question_json, question_set


@pytest.mark.parametrize("code", [item.code for item in load_curriculum().items])
async def test_mock_lesson_for_every_curriculum_item_passes_answer_checks(code):
    plan = await LessonGenerator(MockProvider()).generate(LessonRequest(curriculum_code=code))

    template = load_template("default-tutoring")
    assert [s.section_id for s in plan.sections] == [s.id for s in template.sections]
    questions = [q for s in plan.sections for q in (s.questions or [])]
    assert questions
    assert all(q.check_result.status == CheckStatus.VERIFIED for q in questions)
    tiers = [q.tier.value for q in plan.section("practice").questions]
    assert tiers.count("foundation") == tiers.count("core") == tiers.count("extension") == 3


def test_prompt_contains_all_layers():
    ctx = build_context(
        LessonRequest(curriculum_code="VC2M5N05", extra_context="Use pizza examples")
    )
    prompt = build_section_prompt(ctx, ctx.template.section("parent_note"), {})
    for expected in [
        "'Note for Parents' section",
        "=== LESSON STRUCTURE ===",
        "VC2M5N05",
        "Use pizza examples",
        "Simplified Chinese",
        "Level 5",
        "Return Markdown only",
    ]:
        assert expected in prompt
    assert "${" not in prompt


async def test_wrong_answer_is_sent_back_for_fixing():
    wrong = question_json("7 × 8 = ?", "54", "7*8", "54")
    fixed = question_json("7 × 8 = ?", "56", "7*8", "56")
    provider = ScriptedProvider(
        section_replies={"quiz": [question_set(wrong)]}, fix_replies=[json.dumps(fixed)]
    )
    plan = await LessonGenerator(provider).generate(LessonRequest(curriculum_code="VC2M3N05"))

    quiz = plan.section("quiz").questions
    assert quiz[0].answer == "56"
    assert quiz[0].check_result.status == CheckStatus.VERIFIED
    fix_requests = [r for r in provider.requests if r.meta.get("kind") == "fix"]
    assert len(fix_requests) == 1
    assert "54" in fix_requests[0].prompt and "56" in fix_requests[0].prompt


async def test_unfixable_answer_is_flagged_not_hidden():
    wrong = json.dumps(question_json("7 × 8 = ?", "54", "7*8", "54"))
    provider = ScriptedProvider(
        section_replies={"quiz": [question_set(json.loads(wrong))]},
        fix_replies=[wrong, wrong],
    )
    plan = await LessonGenerator(provider).generate(LessonRequest(curriculum_code="VC2M3N05"))
    assert plan.section("quiz").questions[0].check_result.status == CheckStatus.MISMATCH


async def test_invalid_json_is_retried_then_fails():
    provider = ScriptedProvider(section_replies={"quiz": ["not json", "```json\n{}\n```", "[]"]})
    with pytest.raises(GenerationError):
        await LessonGenerator(provider).generate(LessonRequest(curriculum_code="VC2M3N05"))
    quiz_prompts = [
        r.prompt
        for r in provider.requests
        if r.meta.get("section", None) and r.meta["section"].id == "quiz"
    ]
    assert len(quiz_prompts) == 3
    assert "previous reply was invalid" in quiz_prompts[1]


async def test_fenced_json_is_accepted():
    reply = "```json\n" + question_set(question_json("1 + 1 = ?", "2", "1+1", "2")) + "\n```"
    provider = ScriptedProvider(section_replies={"quiz": [reply]})
    plan = await LessonGenerator(provider).generate(LessonRequest(curriculum_code="VC2M3N05"))
    assert plan.section("quiz").questions[0].answer == "2"


async def test_regenerate_rewrites_only_the_target_section_with_feedback():
    provider = ScriptedProvider()
    generator = LessonGenerator(provider)
    plan = await generator.generate(LessonRequest(curriculum_code="VC2M5N05"))
    provider.requests.clear()

    revised = await generator.regenerate(plan, "teach", "Use a fraction wall")

    assert [r.meta["section"].id for r in provider.requests] == ["teach"]
    prompt = provider.requests[0].prompt
    assert "TEACHER FEEDBACK" in prompt and "Use a fraction wall" in prompt
    assert plan.section("teach").markdown in prompt
    assert revised.section("teach").revision_feedback == ["Use a fraction wall"]
    assert revised.section("practice") == plan.section("practice")
    assert revised.id == plan.id
