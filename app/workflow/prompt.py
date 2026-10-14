import json
import re
from dataclasses import dataclass, field
from textwrap import dedent

from app.models import (
    STUDENT_LEVEL_LABELS,
    CheckResult,
    CurriculumItem,
    LessonRequest,
    OrgConfig,
    OutputType,
    Question,
    SectionDefinition,
    SectionResult,
    WorkflowTemplate,
)

SYSTEM_PROMPT = (
    "You are an experienced Victorian primary school mathematics teacher who writes lesson "
    "materials for private tutoring centres. You follow the Victorian Curriculum 2.0 closely, "
    "use Australian spelling, metric units and AUD, and never copy published exam questions. "
    "You follow the requested output format exactly."
)

MAX_EXTRA_CONTEXT_CHARS = 2000

QUESTION_FORMAT = """\
Return a single JSON object ONLY (no prose, no code fences) shaped like this example:
{
  "questions": [
    {
      "prompt": "A rectangle is 7 cm long and 4 cm wide. What is its area?",
      "tier": "core",
      "answer": "28 cm²",
      "working": "Area = length × width = 7 × 4 = 28 cm²",
      "check": {"expression": "7*4", "expected": "28"},
      "diagram": {"kind": "rectangle", "width": 7, "height": 4, "unit": "cm"}
    }
  ]
}
Rules:
- "tier" is one of "foundation", "core", "extension", or null when the section is not tiered.
- "check" must be present whenever the answer is a single number. "expression" may only use
  digits, decimal points, + - * / and brackets (no units, no variables, no powers, no %).
  "expected" is the final answer as a plain number or fraction, e.g. "28", "3/4" or "0.25".
  Use null for "check" only when the answer is not a single number.
- "diagram" is optional (null if not needed) and must be one of:
  {"kind": "number_line", "start": 0, "end": 2, "step": 0.25, "marks": [0.75], "labels": ["A"],
   "label_style": "fraction"}  (label_style: "fraction", "decimal" or "auto")
  {"kind": "bar_chart", "title": "...", "categories": ["..."], "values": [3, 5], "y_label": "..."}
  {"kind": "rectangle", "width": 7, "height": 4, "unit": "cm"}
"""


@dataclass
class LessonContext:
    request: LessonRequest
    org: OrgConfig
    template: WorkflowTemplate
    item: CurriculumItem
    variables: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.variables = {
            "LEVEL": str(self.item.level),
            "TOPIC": self.item.topic,
            "STUDENT_LEVEL": STUDENT_LEVEL_LABELS[self.request.student_level],
            "DURATION": str(self.request.duration_minutes),
            "OUTPUT_LANGUAGE": self.org.output_language,
            "PARENT_LANGUAGE": self.org.parent_language,
            "ORG_NAME": self.org.name,
            **self.variables,
        }


@dataclass
class Revision:
    previous: SectionResult
    feedback: str


def replace_variables(text: str, variables: dict[str, str]) -> str:
    return re.sub(r"\$\{([A-Z_]+)\}", lambda m: variables.get(m.group(1), m.group(0)), text)


def build_section_prompt(
    ctx: LessonContext,
    section: SectionDefinition,
    dependencies: dict[str, SectionResult],
    revision: Revision | None = None,
) -> str:
    item = ctx.item
    parts: list[str] = []

    # 1. Role: which section of which lesson
    parts.append(
        f"You are writing the '{section.title}' section of a {ctx.request.duration_minutes}-minute "
        f"tutoring lesson for {ctx.org.name}. Students are at Victorian Curriculum Mathematics "
        f"Level {item.level} and are {STUDENT_LEVEL_LABELS[ctx.request.student_level]}. "
        f"Write in {ctx.org.output_language} unless the section description says otherwise."
    )

    # 2. Where this section sits in the lesson
    titles = " -> ".join(s.title for s in ctx.template.sections)
    parts.append(
        "=== LESSON STRUCTURE ===\n"
        f"{titles}\n"
        "The lesson moves students from what they already know to the new idea, then to "
        "independent practice. Build on earlier sections and do not repeat them."
    )

    # 3. Curriculum alignment
    points = "\n".join(f"- {p}" for p in item.teaching_points)
    parts.append(
        "=== CURRICULUM ===\n"
        f"Victorian Curriculum 2.0 Mathematics, {item.strand}, content description {item.code}\n"
        f"Topic: {item.topic}\nFocus: {item.summary}\nTeaching points:\n{points}"
    )

    # 4. Teacher's extra context
    extra = ctx.request.extra_context.strip()
    if extra:
        if len(extra) > MAX_EXTRA_CONTEXT_CHARS:
            extra = extra[:MAX_EXTRA_CONTEXT_CHARS] + " ..."
        parts.append(f"=== NOTES FROM THE TEACHER ===\n{extra}")

    # 5. Sections this one depends on
    if dependencies:
        rendered = "\n\n".join(
            f"--- {d.title} ---\n{d.as_context()}" for d in dependencies.values()
        )
        parts.append(f"=== PREVIOUSLY WRITTEN SECTIONS ===\n{rendered}")

    if revision is not None:
        parts.append(
            "=== PREVIOUS VERSION OF THIS SECTION ===\n"
            f"{revision.previous.as_context()}\n\n"
            "=== TEACHER FEEDBACK ON THE PREVIOUS VERSION ===\n"
            f"{revision.feedback.strip()}\n"
            "Rewrite the section so that it addresses this feedback. Keep what was not criticised."
        )

    # 6. The section's own instructions from the template
    parts.append(
        "=== SECTION INSTRUCTIONS ===\n"
        f"{dedent(section.description).strip()}\n"
        "Follow these instructions exactly."
    )

    # 7. Output format
    if section.output_type == OutputType.QUESTIONS:
        parts.append(f"=== OUTPUT FORMAT ===\n{QUESTION_FORMAT}")
    else:
        parts.append(
            "=== OUTPUT FORMAT ===\nReturn Markdown only: headings with ##/###, bullet lists and "
            "**bold**. Do not wrap the answer in code fences and do not add a title for the "
            "whole section."
        )

    return replace_variables("\n\n".join(parts), ctx.variables)


def build_fix_prompt(question: Question, result: CheckResult) -> str:
    payload = question.model_dump(mode="json", exclude={"check_result"})
    return (
        "A worksheet question failed an automatic answer check.\n"
        f"Problem found: {result.message}\n\n"
        f"Question JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Fix the question so that the answer, working and check are all correct and consistent. "
        "Keep the same skill, tier and difficulty. Return the corrected question as a single JSON "
        "object with the same fields (no prose, no code fences). The check expression may only "
        "use digits, decimal points, + - * / and brackets."
    )
