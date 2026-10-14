import logging
from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.data_loader import list_orgs, load_curriculum
from app.export.docx_export import build_docx
from app.llm.provider import LLMProvider, get_provider
from app.models import STUDENT_LEVEL_LABELS, CheckStatus, LessonPlan, LessonRequest, StudentLevel
from app.render.diagrams import render_diagram, to_data_uri
from app.render.markdown_blocks import markdown_to_html
from app.workflow.engine import GenerationError, LessonGenerator, build_context

logger = logging.getLogger(__name__)

MAX_STORED_PLANS = 200
MAX_FEEDBACK_CHARS = 1000

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["markdown"] = markdown_to_html
templates.env.filters["diagram_uri"] = lambda d: to_data_uri(render_diagram(d))
templates.env.globals["CheckStatus"] = CheckStatus
templates.env.globals["STUDENT_LEVEL_LABELS"] = STUDENT_LEVEL_LABELS


class PlanStore:
    """In-memory store for the demo; replaced by Postgres in the next phase."""

    def __init__(self, capacity: int = MAX_STORED_PLANS):
        self._plans: OrderedDict[str, LessonPlan] = OrderedDict()
        self._capacity = capacity

    def save(self, plan: LessonPlan) -> None:
        self._plans[plan.id] = plan
        self._plans.move_to_end(plan.id)
        while len(self._plans) > self._capacity:
            self._plans.popitem(last=False)

    def get(self, plan_id: str) -> LessonPlan:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Lesson plan not found")
        return plan


def _validate(request: LessonRequest) -> None:
    try:
        build_context(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown id: {exc.args[0]}") from exc


def create_app(provider: LLMProvider | None = None) -> FastAPI:
    app = FastAPI(title="Teaching Agent")
    generator = LessonGenerator(provider or get_provider(get_settings()))
    store = PlanStore()

    def plan_view(request: Request, plan: LessonPlan, template_name: str, **extra):
        ctx = build_context(plan.request)
        return templates.TemplateResponse(
            request,
            template_name,
            {"plan": plan, "item": ctx.item, "org": ctx.org, "template": ctx.template, **extra},
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        curriculum = load_curriculum()
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "orgs": list_orgs(),
                "curriculum": curriculum,
                "levels": curriculum.levels(),
                "student_levels": list(StudentLevel),
                "provider": generator.provider.name,
            },
        )

    @app.post("/generate", response_class=HTMLResponse)
    async def generate(
        request: Request,
        curriculum_code: Annotated[str, Form()],
        org_id: Annotated[str, Form()] = "demo-org",
        student_level: Annotated[StudentLevel, Form()] = StudentLevel.CORE,
        duration_minutes: Annotated[int, Form(ge=30, le=180)] = 60,
        extra_context: Annotated[str, Form(max_length=4000)] = "",
    ):
        lesson_request = LessonRequest(
            org_id=org_id,
            curriculum_code=curriculum_code,
            student_level=student_level,
            duration_minutes=duration_minutes,
            extra_context=extra_context,
        )
        _validate(lesson_request)
        try:
            plan = await generator.generate(lesson_request)
        except GenerationError as exc:
            logger.exception("Generation failed")
            # HTMX only swaps 2xx responses into the page.
            return templates.TemplateResponse(request, "partials/error.html", {"message": str(exc)})
        store.save(plan)
        return plan_view(request, plan, "partials/plan.html")

    @app.post("/plans/{plan_id}/sections/{section_id}/regenerate", response_class=HTMLResponse)
    async def regenerate(
        request: Request,
        plan_id: str,
        section_id: str,
        feedback: Annotated[str, Form(min_length=1, max_length=MAX_FEEDBACK_CHARS)],
    ):
        plan = store.get(plan_id)
        try:
            plan.section(section_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Section not found") from exc
        try:
            plan = await generator.regenerate(plan, section_id, feedback)
        except GenerationError as exc:
            logger.exception("Regeneration failed")
            return plan_view(
                request,
                plan,
                "partials/section.html",
                section=plan.section(section_id),
                error=str(exc),
            )
        store.save(plan)
        return plan_view(request, plan, "partials/section.html", section=plan.section(section_id))

    @app.get("/export/{plan_id}.docx")
    async def export_docx(plan_id: str, variant: Literal["teacher", "student"] = "teacher"):
        plan = store.get(plan_id)
        ctx = build_context(plan.request)
        content = build_docx(plan, ctx.org, ctx.item, ctx.template, variant)
        filename = f"{ctx.item.code}-{variant}-{plan.id}.docx"
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/plans", response_model=LessonPlan)
    async def api_create_plan(lesson_request: LessonRequest):
        _validate(lesson_request)
        try:
            plan = await generator.generate(lesson_request)
        except GenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        store.save(plan)
        return plan

    @app.get("/api/plans/{plan_id}", response_model=LessonPlan)
    async def api_get_plan(plan_id: str):
        return store.get(plan_id)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "provider": generator.provider.name}

    return app


app = create_app()
