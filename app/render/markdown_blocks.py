"""Small Markdown subset shared by the HTML preview and the Word export.

Supports ##/### headings, bullet and numbered lists, paragraphs, **bold** and _italic_.
"""

import re
from dataclasses import dataclass, field
from html import escape
from typing import Literal

from markupsafe import Markup

_INLINE = re.compile(r"(\*\*[^*]+\*\*|(?<!\w)_[^_]+_(?!\w))")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Block:
    kind: Literal["heading", "paragraph", "bullet", "numbered"]
    runs: list[Run] = field(default_factory=list)
    level: int = 0


def parse_inline(text: str) -> list[Run]:
    runs = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            runs.append(Run(part[2:-2], bold=True))
        elif part.startswith("_") and part.endswith("_") and len(part) > 2:
            runs.append(Run(part[1:-1], italic=True))
        else:
            runs.append(Run(part))
    return runs


def parse_markdown(text: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block("paragraph", parse_inline(" ".join(paragraph))))
            paragraph.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
        elif m := _HEADING.match(line):
            flush()
            blocks.append(Block("heading", parse_inline(m.group(2)), level=len(m.group(1))))
        elif m := _BULLET.match(line):
            flush()
            blocks.append(Block("bullet", parse_inline(m.group(1))))
        elif m := _NUMBERED.match(line):
            flush()
            blocks.append(Block("numbered", parse_inline(m.group(1))))
        else:
            paragraph.append(line.strip())
    flush()
    return blocks


def _runs_html(runs: list[Run]) -> str:
    out = []
    for run in runs:
        text = escape(run.text)
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        out.append(text)
    return "".join(out)


def markdown_to_html(text: str) -> Markup:
    html: list[str] = []
    open_list: str | None = None
    for block in parse_markdown(text):
        tag = {"bullet": "ul", "numbered": "ol"}.get(block.kind)
        if open_list and tag != open_list:
            html.append(f"</{open_list}>")
            open_list = None
        if tag and not open_list:
            html.append(f"<{tag}>")
            open_list = tag
        if tag:
            html.append(f"<li>{_runs_html(block.runs)}</li>")
        elif block.kind == "heading":
            level = min(max(block.level + 1, 3), 5)
            html.append(f"<h{level}>{_runs_html(block.runs)}</h{level}>")
        else:
            html.append(f"<p>{_runs_html(block.runs)}</p>")
    if open_list:
        html.append(f"</{open_list}>")
    return Markup("".join(html))
