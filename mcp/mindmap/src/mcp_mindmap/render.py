"""Pure-Python rendering of a mind-map node tree.

Two outputs:
  - **Mermaid** text using the ``mindmap`` directive — renderable in
    Markdown viewers and the web client (M-8).
  - **SVG** with a simple radial layout — readable in any browser, used
    by the CLI demo so we don't need Node + headless Chrome.

Schema: a node dict like
    {"text": "Cloud", "children": [{"text": "Compute", "children": [...]}]}
"""

from __future__ import annotations

import math
import xml.sax.saxutils as _xml
from typing import Any

# ---- Mermaid ---------------------------------------------------------


def to_mermaid(node: dict[str, Any]) -> str:
    lines = ["mindmap"]
    _walk_mermaid(node, depth=1, out=lines)
    return "\n".join(lines)


def _walk_mermaid(node: dict[str, Any], *, depth: int, out: list[str]) -> None:
    indent = "  " * depth
    text = str(node.get("text", "")).replace("\n", " ").strip()
    if depth == 1:
        out.append(f"{indent}root(({text}))")
    else:
        out.append(f"{indent}{text}")
    for child in node.get("children", []) or []:
        _walk_mermaid(child, depth=depth + 1, out=out)


# ---- SVG (radial) ----------------------------------------------------


def to_svg(
    node: dict[str, Any],
    *,
    width: int = 1000,
    height: int = 700,
) -> str:
    """Lay out the tree radially: root in centre, children on a ring,
    grandchildren on a wider ring along the same angle.

    Pure Python, no external libs. Output is well-formed XML.
    """
    cx, cy = width / 2, height / 2
    inner_radius = min(width, height) * 0.22
    outer_radius = min(width, height) * 0.42

    elements: list[str] = []
    elements.append(_circle(cx, cy, 50, fill="#1f2937"))
    elements.append(_text(cx, cy + 4, str(node.get("text", "")), fill="white", size=14))

    children = node.get("children", []) or []
    if children:
        for i, child in enumerate(children):
            angle = (2 * math.pi * i) / len(children) - math.pi / 2
            x1 = cx + inner_radius * math.cos(angle)
            y1 = cy + inner_radius * math.sin(angle)
            elements.append(_line(cx, cy, x1, y1, stroke="#94a3b8", width=2))
            elements.append(_circle(x1, y1, 36, fill="#3b82f6"))
            elements.append(_text(x1, y1 + 4, str(child.get("text", "")), fill="white", size=12))

            grand = child.get("children", []) or []
            if not grand:
                continue
            spread = math.pi / 4
            base = angle - spread / 2
            for j, leaf in enumerate(grand):
                step = spread / max(len(grand) - 1, 1) if len(grand) > 1 else 0
                a = base + j * step
                x2 = cx + outer_radius * math.cos(a)
                y2 = cy + outer_radius * math.sin(a)
                elements.append(_line(x1, y1, x2, y2, stroke="#cbd5e1", width=1))
                elements.append(_circle(x2, y2, 6, fill="#22c55e"))
                elements.append(
                    _text(
                        x2 + 10 if math.cos(a) >= 0 else x2 - 10,
                        y2 + 4,
                        str(leaf.get("text", "")),
                        fill="#0f172a",
                        size=11,
                        anchor="start" if math.cos(a) >= 0 else "end",
                    )
                )

    body = "\n  ".join(elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n  '
        f'<rect width="{width}" height="{height}" fill="#f8fafc"/>\n  '
        f"{body}\n"
        "</svg>\n"
    )


def _circle(cx: float, cy: float, r: float, *, fill: str) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>'


def _line(x1: float, y1: float, x2: float, y2: float, *, stroke: str, width: int) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}"/>'
    )


def _text(
    x: float,
    y: float,
    text: str,
    *,
    fill: str,
    size: int,
    anchor: str = "middle",
) -> str:
    safe = _xml.escape(text)
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Inter, system-ui, sans-serif" '
        f'font-size="{size}" fill="{fill}">{safe}</text>'
    )
