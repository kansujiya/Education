"""Pure-logic tests for the bundle assembler."""

from __future__ import annotations

import io
import json
import zipfile

from mcp_pdf.bundle import build_zip
from mcp_pdf.server import bundle_markdown_zip

CARDS = [
    {
        "type": "recall",
        "prompt": "What is pay-as-you-go?",
        "answer": "Pay only for what you use; no upfront commitment.",
        "key_points": ["pay-as-you-go"],
        "source_pyq_id": "pyq_001",
        "source_year": 2023,
    }
]


def test_build_zip_contains_all_files() -> None:
    raw = build_zip(
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits of the Cloud",
        lesson_md="# Lesson\n\nThe cloud rents capacity.\n",
        mindmap_svg='<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>',
        mindmap_mermaid="mindmap\n  root((Benefits))\n",
        cards=CARDS,
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert names == {
            "README.md",
            "lesson.md",
            "mindmap.svg",
            "mindmap.mmd",
            "cards.json",
            "cards.md",
        }
        assert "Benefits of the Cloud" in zf.read("README.md").decode()
        assert "rents capacity" in zf.read("lesson.md").decode()
        assert "<svg" in zf.read("mindmap.svg").decode()
        assert "mindmap" in zf.read("mindmap.mmd").decode()
        loaded = json.loads(zf.read("cards.json"))
        assert loaded == CARDS
        cheat = zf.read("cards.md").decode()
        assert "Q." in cheat and "A." in cheat


def test_bundle_markdown_zip_returns_b64() -> None:
    out = bundle_markdown_zip(
        topic_id="x",
        topic_title="X",
        lesson_md="hi",
        mindmap_svg="<svg/>",
        mindmap_mermaid="mindmap",
        cards=[],
    )
    assert out["format"] == "zip"
    assert out["size_bytes"] > 0
    # Decoding the base64 should give a valid ZIP.
    import base64

    raw = base64.b64decode(out["base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "README.md" in zf.namelist()


def test_empty_cards_produces_friendly_message() -> None:
    raw = build_zip(
        topic_id="x",
        topic_title="X",
        lesson_md="",
        mindmap_svg="<svg/>",
        mindmap_mermaid="",
        cards=[],
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "no cards generated yet" in zf.read("cards.md").decode()
