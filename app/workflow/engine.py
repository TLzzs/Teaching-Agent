import asyncio
import logging
import re

from pydantic import ValidationError

from app.data_loader import load_curriculum, load_org, load_template
from app.llm.provider import CompletionRequest, LLMProvider
from app.models import (
    CheckStatus,
    LessonPlan,
    LessonRequest,
    OutputType,
    Question,
    QuestionSet,
    SectionDefinition,
    SectionResult,
)
from app.verify.math_check import check_question, evaluate
from app.workflow.dag import run_dag
from app.workflow.prompt import (
    SYSTEM_PROMPT,
    LessonContext,
    Revision,
    build_fix_prompt,
    build_section_prompt,
)

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class GenerationError(RuntimeError):
    pass


def strip_fences(text: str) -> str:
    return _FENCE.sub("", text.strip()).strip()


def build_context(request: LessonRequest) -> LessonContext:
    org = load_org(request.org_id)
    return LessonContext(
        request=request,
        org=org,
        template=load_template(org.template_id),
        item=load_curriculum().item(request.curriculum_code),
    )


class LessonGenerator:
    def __init__(self, provider: LLMProvider, max_attempts: int = 3, max_fix_attempts: int = 2):
        self.provider = provider
        self.max_attempts = max_attempts
        self.max_fix_attempts = max_fix_attempts

    async def generate(self, request: LessonRequest) -> LessonPlan:
        ctx = build_context(request)

        async def generate_section(section, deps):
            return await self._generate_section(ctx, section, deps)

        results = await run_dag(ctx.template.sections, generate_section)
        return LessonPlan(
            request=request,
            template_id=ctx.template.id,
            provider=self.provider.name,
            sections=[results[s.id] for s in ctx.template.sections],
        )

    async def regenerate(self, plan: LessonPlan, section_id: str, feedback: str) -> LessonPlan:
        """Rewrite one section using the teacher's feedback; every other section is kept."""
        ctx = build_context(plan.request)
        previous = plan.section(section_id)
        completed = {s.section_id: s for s in plan.sections if s.section_id != section_id}
        revision = Revision(previous=previous, feedback=feedback)

        async def generate_section(section, deps):
            result = await self._generate_section(ctx, section, deps, revision)
            result.revision_feedback = [*previous.revision_feedback, feedback]
            return result

        results = await run_dag(ctx.template.sections, generate_section, completed)
        return plan.model_copy(
            update={"sections": [results[s.id] for s in ctx.template.sections]}
        )

    async def _generate_section(
        self,
        ctx: LessonContext,
        section: SectionDefinition,
        deps: dict[str, SectionResult],
        revision: Revision | None = None,
    ) -> SectionResult:
        request = CompletionRequest(
            system=SYSTEM_PROMPT,
            prompt=build_section_prompt(ctx, section, deps, revision),
            json_mode=section.output_type == OutputType.QUESTIONS,
            meta={
                "kind": "section",
                "section": section,
                "item": ctx.item,
                "student_level": ctx.request.student_level,
                "parent_language": ctx.org.parent_language,
                "feedback": revision.feedback if revision else None,
            },
        )
        result = SectionResult(
            section_id=section.id, title=section.title, output_type=section.output_type
        )
        if section.output_type == OutputType.MARKDOWN:
            result.markdown = strip_fences(await self.provider.complete(request))
            return result

        question_set = await self._complete_questions(request)
        result.questions = list(
            await asyncio.gather(*(self._verify(q) for q in question_set.questions))
        )
        return result

    async def _complete_questions(self, request: CompletionRequest) -> QuestionSet:
        prompt = request.prompt
        last_error = ""
        for _ in range(self.max_attempts):
            request.prompt = prompt + (f"\n\nYour previous reply was invalid: {last_error}"
                                       if last_error else "")
            raw = await self.provider.complete(request)
            try:
                question_set = QuestionSet.model_validate_json(strip_fences(raw))
            except ValidationError as exc:
                last_error = exc.errors()[0]["msg"] if exc.errors() else str(exc)
                logger.warning("Invalid question JSON: %s", last_error)
                continue
            if question_set.questions:
                return question_set
            last_error = "the questions list was empty"
        raise GenerationError(f"Model did not return valid questions: {last_error}")

    async def _verify(self, question: Question) -> Question:
        """Recompute the answer; ask the model to fix the question when it does not match."""
        result = check_question(question)
        question.check_result = result
        attempts = 0
        while result.status in (CheckStatus.MISMATCH, CheckStatus.INVALID):
            if attempts >= self.max_fix_attempts:
                break
            attempts += 1
            computed = None
            if question.check is not None and result.status == CheckStatus.MISMATCH:
                computed = str(evaluate(question.check.expression))
            raw = await self.provider.complete(
                CompletionRequest(
                    system=SYSTEM_PROMPT,
                    prompt=build_fix_prompt(question, result),
                    json_mode=True,
                    meta={"kind": "fix", "question": question, "computed": computed},
                )
            )
            try:
                candidate = Question.model_validate_json(strip_fences(raw))
            except ValidationError:
                continue
            candidate_result = check_question(candidate)
            candidate.check_result = candidate_result
            question, result = candidate, candidate_result
        return question
