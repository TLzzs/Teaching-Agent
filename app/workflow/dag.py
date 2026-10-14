import asyncio
from collections.abc import Awaitable, Callable

from app.models import SectionDefinition, SectionResult

GenerateFn = Callable[[SectionDefinition, dict[str, SectionResult]], Awaitable[SectionResult]]


class WorkflowError(ValueError):
    pass


def validate_sections(sections: list[SectionDefinition]) -> None:
    ids = [s.id for s in sections]
    if len(ids) != len(set(ids)):
        raise WorkflowError("Duplicate section ids in template")
    known = set(ids)
    for section in sections:
        missing = [d for d in section.dependencies if d not in known]
        if missing:
            raise WorkflowError(f"Section '{section.id}' depends on unknown sections {missing}")


async def run_dag(
    sections: list[SectionDefinition],
    generate: GenerateFn,
    completed: dict[str, SectionResult] | None = None,
) -> dict[str, SectionResult]:
    """Generate every section once its dependencies are done; independent sections run in parallel.

    Sections already present in `completed` are kept as-is and only serve as dependencies.
    """
    validate_sections(sections)
    results = dict(completed or {})
    pending = {s.id: s for s in sections if s.id not in results}

    while pending:
        ready = [s for s in pending.values() if all(d in results for d in s.dependencies)]
        if not ready:
            raise WorkflowError(f"Cycle detected among sections {sorted(pending)}")
        outputs = await asyncio.gather(
            *(generate(s, {d: results[d] for d in s.dependencies}) for s in ready)
        )
        for section, output in zip(ready, outputs, strict=True):
            results[section.id] = output
            del pending[section.id]

    return results
