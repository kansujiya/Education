"""Pure-Python bundle assembly.

Given lesson markdown, a mindmap SVG and a list of cards (dicts), produce
a ZIP archive containing:

  - lesson.md       — the streamed Tutor lesson with cited sources
  - mindmap.svg     — the radial mind map
  - mindmap.mmd     — Mermaid source (web client renders this in M-8)
  - cards.json      — card list (prompt, answer, key_points, source)
  - cards.md        — same cards rendered as a printable cheat-sheet
  - README.md       — what's in this bundle

Returned as raw bytes; storing them in S3 / a file is the caller's job.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any


def build_zip(
    *,
    topic_id: str,
    topic_title: str,
    lesson_md: str,
    mindmap_svg: str,
    mindmap_mermaid: str,
    cards: list[dict[str, Any]],
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", _readme(topic_id, topic_title, len(cards)))
        zf.writestr("lesson.md", lesson_md)
        zf.writestr("mindmap.svg", mindmap_svg)
        zf.writestr("mindmap.mmd", mindmap_mermaid)
        zf.writestr("cards.json", json.dumps(cards, indent=2, sort_keys=True))
        zf.writestr("cards.md", _cards_to_markdown(cards))
    return buf.getvalue()


def _readme(topic_id: str, topic_title: str, n_cards: int) -> str:
    return (
        f"# {topic_title}\n"
        f"Topic id: `{topic_id}`\n\n"
        "Files in this bundle:\n\n"
        "- `lesson.md` — layman explanation streamed by the Tutor agent.\n"
        "- `mindmap.svg` — radial mind map (open in any browser).\n"
        "- `mindmap.mmd` — Mermaid source (paste into mermaid.live or "
        "the web client to re-render).\n"
        "- `cards.md` — printable flash-card / MCQ cheat-sheet "
        f"({n_cards} cards).\n"
        "- `cards.json` — the same cards as machine-readable JSON.\n"
    )


def _cards_to_markdown(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "# Cards\n\n(no cards generated yet — run `edu cards` first)\n"
    lines = ["# Cards", ""]
    for i, c in enumerate(cards, start=1):
        kind = c.get("type", "")
        prompt = c.get("prompt", "")
        answer = c.get("answer", "")
        kp = c.get("key_points") or []
        src_id = c.get("source_pyq_id") or ""
        src_year = c.get("source_year") or ""
        src_label = (
            f" (source: {src_id}{', ' + str(src_year) if src_year else ''})" if src_id else ""
        )

        lines.append(f"## {i}. {kind.upper()}{src_label}")
        lines.append("")
        lines.append(f"**Q.** {prompt}")
        lines.append("")
        lines.append(f"**A.** {answer}")
        if kp:
            lines.append("")
            lines.append(f"**Key points:** {', '.join(kp)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
