"""Pure-logic tests for mcp-syllabus.

These exercise the underlying functions directly without spawning the
MCP transport. Round-trip-via-subprocess is covered separately in the
api integration tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp_syllabus.server import (
    _flatten,
    _load_exam,
    diff_syllabus,
    fetch_syllabus,
    parse_syllabus,
)
from shared.models import SyllabusTopic

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _seeds_dir(monkeypatch):
    monkeypatch.setenv("MCP_SYLLABUS_DATA_DIR", str(REPO / "seeds"))
    _load_exam.cache_clear()


def test_fetch_returns_topic_tree() -> None:
    out = fetch_syllabus("aws-ccp")
    assert out["exam_id"] == "aws-ccp"
    titles = {t["title"] for t in out["topics"]}
    assert "Cloud Concepts" in titles
    # Children populated.
    cloud = next(t for t in out["topics"] if t["id"] == "cloud-concepts")
    assert any(c["id"] == "cloud-concepts.benefits" for c in cloud["children"])


def test_fetch_unknown_exam_raises() -> None:
    with pytest.raises(FileNotFoundError):
        fetch_syllabus("nope-2099")


def test_parse_round_trip() -> None:
    raw = '{"topics":[{"id":"x","title":"X","weight":0.5}]}'
    out = parse_syllabus(raw, exam_id="aws-ccp")
    assert out["topics"][0]["id"] == "x"
    assert out["topics"][0]["exam_id"] == "aws-ccp"


def test_diff_detects_added_removed_renamed() -> None:
    old = [SyllabusTopic(id="a", exam_id="x", title="Alpha").model_dump()]
    new = [
        SyllabusTopic(id="a", exam_id="x", title="Alpha-renamed").model_dump(),
        SyllabusTopic(id="b", exam_id="x", title="Beta").model_dump(),
    ]
    out = diff_syllabus(old, new)
    assert out["added"] == ["b"]
    assert out["removed"] == []
    assert out["renamed"] == [("Alpha", "Alpha-renamed")]


def test_flatten_includes_descendants() -> None:
    tree = [
        SyllabusTopic(
            id="root",
            exam_id="x",
            title="Root",
            children=[SyllabusTopic(id="leaf", exam_id="x", parent_id="root", title="Leaf")],
        )
    ]
    flat = _flatten(tree)
    assert set(flat) == {"root", "leaf"}
