from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class OutputType(StrEnum):
    MARKDOWN = "markdown"
    QUESTIONS = "questions"


class StudentLevel(StrEnum):
    FOUNDATION = "foundation"
    CORE = "core"
    EXTENSION = "extension"


STUDENT_LEVEL_LABELS = {
    StudentLevel.FOUNDATION: "foundation (needs consolidation)",
    StudentLevel.CORE: "core (working at level)",
    StudentLevel.EXTENSION: "extension (working above level)",
}


# --- Configuration loaded from data/ ---------------------------------------------------------


class SectionDefinition(BaseModel):
    id: str
    title: str
    description: str = Field(description="How to write this section; supports ${VAR} placeholders")
    output_type: OutputType = OutputType.MARKDOWN
    dependencies: list[str] = Field(default_factory=list)
    student_facing: bool = False
    answers_in_student_copy: bool = False


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str = ""
    sections: list[SectionDefinition]

    def section(self, section_id: str) -> SectionDefinition:
        for section in self.sections:
            if section.id == section_id:
                return section
        raise KeyError(section_id)


class CurriculumItem(BaseModel):
    code: str
    level: int
    strand: str
    topic: str
    summary: str = Field(description="Paraphrase written for this product, not VCAA text")
    teaching_points: list[str] = Field(default_factory=list)


class Curriculum(BaseModel):
    framework: str
    subject: str
    source_url: str
    notice: str
    items: list[CurriculumItem]

    def item(self, code: str) -> CurriculumItem:
        for item in self.items:
            if item.code == code:
                return item
        raise KeyError(code)

    def levels(self) -> list[int]:
        return sorted({item.level for item in self.items})


class OrgConfig(BaseModel):
    id: str
    name: str
    tagline: str = ""
    primary_color: str = "#1F4E79"
    logo_path: str | None = None
    footer_text: str = ""
    template_id: str = "default-tutoring"
    output_language: str = "English"
    parent_language: str = "English"


# --- Generated content -----------------------------------------------------------------------


class NumberLine(BaseModel):
    kind: Literal["number_line"] = "number_line"
    start: float
    end: float
    step: float
    marks: list[float] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    label_style: Literal["auto", "fraction", "decimal"] = "auto"


class BarChart(BaseModel):
    kind: Literal["bar_chart"] = "bar_chart"
    title: str = ""
    categories: list[str]
    values: list[float]
    y_label: str = ""


class Rectangle(BaseModel):
    kind: Literal["rectangle"] = "rectangle"
    width: float
    height: float
    unit: str = "cm"


Diagram = Annotated[NumberLine | BarChart | Rectangle, Field(discriminator="kind")]


class MathCheck(BaseModel):
    expression: str = Field(description="Arithmetic expression whose value is the answer")
    expected: str = Field(description="The answer as a plain number or fraction, no units")


class CheckStatus(StrEnum):
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    INVALID = "invalid"
    NOT_CHECKABLE = "not_checkable"


class CheckResult(BaseModel):
    status: CheckStatus
    computed: str | None = None
    message: str = ""


class Question(BaseModel):
    prompt: str
    tier: StudentLevel | None = None
    answer: str
    working: str = ""
    check: MathCheck | None = None
    diagram: Diagram | None = None
    check_result: CheckResult | None = None


class QuestionSet(BaseModel):
    questions: list[Question]


class SectionResult(BaseModel):
    section_id: str
    title: str
    output_type: OutputType
    markdown: str | None = None
    questions: list[Question] | None = None
    revision_feedback: list[str] = Field(default_factory=list)

    def as_context(self) -> str:
        if self.output_type == OutputType.MARKDOWN:
            return self.markdown or ""
        lines = []
        for i, q in enumerate(self.questions or [], start=1):
            tier = f"[{q.tier.value}] " if q.tier else ""
            lines.append(f"{i}. {tier}{q.prompt} (answer: {q.answer})")
        return "\n".join(lines)


class LessonRequest(BaseModel):
    org_id: str = "demo-org"
    curriculum_code: str
    student_level: StudentLevel = StudentLevel.CORE
    duration_minutes: int = Field(default=60, ge=30, le=180)
    extra_context: str = Field(default="", max_length=4000)


class LessonPlan(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    request: LessonRequest
    template_id: str
    provider: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sections: list[SectionResult]

    def section(self, section_id: str) -> SectionResult:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise KeyError(section_id)
