import asyncio

import pytest

from app.models import OutputType, SectionDefinition, SectionResult
from app.workflow.dag import WorkflowError, run_dag


def section(section_id: str, *deps: str) -> SectionDefinition:
    return SectionDefinition(
        id=section_id, title=section_id, description="", dependencies=list(deps)
    )


def result(section_id: str, text: str) -> SectionResult:
    return SectionResult(
        section_id=section_id, title=section_id, output_type=OutputType.MARKDOWN, markdown=text
    )


async def test_runs_in_dependency_order_and_passes_dependency_outputs():
    seen: dict[str, list[str]] = {}

    async def generate(s, deps):
        seen[s.id] = sorted(deps)
        return result(s.id, "+".join([s.id, *(d.markdown for d in deps.values())]))

    sections = [section("c", "a", "b"), section("a"), section("b", "a")]
    results = await run_dag(sections, generate)

    assert seen == {"a": [], "b": ["a"], "c": ["a", "b"]}
    assert results["c"].markdown == "c+a+b+a"


async def test_independent_sections_run_concurrently():
    running = 0
    peak = 0

    async def generate(s, deps):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return result(s.id, s.id)

    await run_dag([section("a"), section("b"), section("c"), section("d", "a", "b", "c")], generate)
    assert peak == 3


async def test_completed_sections_are_not_regenerated():
    calls = []

    async def generate(s, deps):
        calls.append(s.id)
        return result(s.id, "new")

    results = await run_dag(
        [section("a"), section("b", "a")], generate, completed={"a": result("a", "kept")}
    )
    assert calls == ["b"]
    assert results["a"].markdown == "kept"


@pytest.mark.parametrize(
    "sections",
    [
        [section("a", "b"), section("b", "a")],
        [section("a", "missing")],
        [section("a"), section("a")],
    ],
)
async def test_invalid_workflows_are_rejected(sections):
    async def generate(s, deps):
        return result(s.id, "")

    with pytest.raises(WorkflowError):
        await run_dag(sections, generate)
