import base64
import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from app.models import BarChart, NumberLine, Rectangle  # noqa: E402

MAX_TICKS = 41


def _to_png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _tick_label(value: float, step: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(round(value))
    denominator = round(1 / step)
    if denominator > 1 and abs(1 / step - denominator) < 1e-6 and (step * 100) % 1 > 1e-9:
        return f"{round(value * denominator)}/{denominator}"
    return f"{value:.3f}".rstrip("0")


def render_number_line(diagram: NumberLine) -> bytes:
    start, end = min(diagram.start, diagram.end), max(diagram.start, diagram.end)
    step = diagram.step if diagram.step > 0 else 1
    count = int(round((end - start) / step)) + 1
    if count > MAX_TICKS:
        step = (end - start) / (MAX_TICKS - 1)
        count = MAX_TICKS

    fig, ax = plt.subplots(figsize=(6.5, 1.1))
    ax.plot([start, end], [0, 0], color="black", linewidth=1.5)
    for i in range(count):
        x = start + i * step
        ax.plot([x, x], [-0.08, 0.08], color="black", linewidth=1)
        ax.text(x, -0.25, _tick_label(x, step), ha="center", va="top", fontsize=8)
    for i, mark in enumerate(diagram.marks):
        ax.plot(mark, 0, "o", color="#DC2626", markersize=7)
        if i < len(diagram.labels):
            ax.text(mark, 0.2, diagram.labels[i], ha="center", va="bottom", fontsize=9)
    ax.set_xlim(start - step / 2, end + step / 2)
    ax.set_ylim(-0.6, 0.5)
    ax.axis("off")
    return _to_png(fig)


def render_bar_chart(diagram: BarChart) -> bytes:
    pairs = list(zip(diagram.categories, diagram.values, strict=False))
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar([p[0] for p in pairs], [p[1] for p in pairs], color="#60A5FA", edgecolor="#1E3A8A")
    ax.set_title(diagram.title, fontsize=10)
    ax.set_ylabel(diagram.y_label, fontsize=9)
    ax.yaxis.grid(True, linestyle=":", alpha=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8)
    if pairs:
        ax.set_yticks(range(0, int(max(p[1] for p in pairs)) + 2))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return _to_png(fig)


def render_rectangle(diagram: Rectangle) -> bytes:
    w, h = max(diagram.width, 0.1), max(diagram.height, 0.1)
    scale = 4 / max(w, h)
    sw, sh = w * scale, h * scale
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.add_patch(
        FancyBboxPatch(
            (0, 0), sw, sh, boxstyle="square,pad=0", fill=False, edgecolor="black", linewidth=1.5
        )
    )
    ax.text(sw / 2, -0.25, f"{w:g} {diagram.unit}", ha="center", va="top", fontsize=10)
    ax.text(sw + 0.2, sh / 2, f"{h:g} {diagram.unit}", ha="left", va="center", fontsize=10)
    ax.set_xlim(-0.5, sw + 1.5)
    ax.set_ylim(-0.8, sh + 0.4)
    ax.set_aspect("equal")
    ax.axis("off")
    return _to_png(fig)


def render_diagram(diagram: NumberLine | BarChart | Rectangle) -> bytes:
    if isinstance(diagram, NumberLine):
        return render_number_line(diagram)
    if isinstance(diagram, BarChart):
        return render_bar_chart(diagram)
    return render_rectangle(diagram)


def render_logo(name: str, color: str) -> bytes:
    """Placeholder logo built from the organisation's initials, used when no logo file is set."""
    initials = "".join(word[0] for word in name.split() if word[:1].isalpha())[:3].upper()
    fig, ax = plt.subplots(figsize=(1.2, 1.2))
    ax.add_patch(
        FancyBboxPatch(
            (0.05, 0.05), 0.9, 0.9, boxstyle="round,pad=0,rounding_size=0.2", color=color
        )
    )
    ax.text(
        0.5, 0.5, initials, ha="center", va="center", color="white", fontsize=22, fontweight="bold"
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return _to_png(fig)


def to_data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
