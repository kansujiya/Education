"""MCP server exposing syllabus tools.

The server runs over stdio so any MCP client can spawn it as a subprocess.
For v0.1 the corpus is a small JSON file per exam under ``seeds/``.

Run via:
    python -m mcp_syllabus.server
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from shared.models import SyllabusTopic
from shared.tools import (
    DiffSyllabusOutput,
    FetchSyllabusOutput,
    ParseSyllabusOutput,
)


def _data_dir() -> Path:
    return Path(os.environ.get("MCP_SYLLABUS_DATA_DIR", "seeds")).resolve()


@lru_cache(maxsize=32)
def _load_exam(exam_id: str) -> FetchSyllabusOutput:
    path = _data_dir() / f"exam_{exam_id.replace('-', '_')}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown exam_id={exam_id!r}; expected file {path}")
    raw = json.loads(path.read_text())
    return FetchSyllabusOutput(
        exam_id=raw["exam_id"],
        name=raw["name"],
        topics=[_to_topic(t, raw["exam_id"]) for t in raw["topics"]],
    )


def _to_topic(node: dict[str, Any], exam_id: str, parent_id: str | None = None) -> SyllabusTopic:
    return SyllabusTopic(
        id=node["id"],
        exam_id=exam_id,
        parent_id=parent_id,
        title=node["title"],
        weight=node.get("weight", 1.0),
        children=[_to_topic(c, exam_id, node["id"]) for c in node.get("children", [])],
    )


def _flatten(topics: list[SyllabusTopic]) -> dict[str, SyllabusTopic]:
    flat: dict[str, SyllabusTopic] = {}
    stack = list(topics)
    while stack:
        t = stack.pop()
        flat[t.id] = t
        stack.extend(t.children)
    return flat


# ---- Server -----------------------------------------------------------

mcp_server = FastMCP("syllabus")


@mcp_server.tool()
def fetch_syllabus(exam_id: str) -> dict[str, Any]:
    """Return the topic tree for a given exam."""
    return _load_exam(exam_id).model_dump()


@mcp_server.tool()
def parse_syllabus(raw: str, exam_id: str) -> dict[str, Any]:
    """Parse a JSON syllabus blob into the canonical topic-tree shape.

    v0.1 expects the same JSON shape as our seed files. A future iteration
    can accept Markdown / HTML and extract structure with the LLM.
    """
    data = json.loads(raw)
    topics = [_to_topic(t, exam_id) for t in data.get("topics", [])]
    return ParseSyllabusOutput(topics=topics).model_dump()


@mcp_server.tool()
def diff_syllabus(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute added/removed/renamed sets between two topic trees by ID."""
    old_topics = [SyllabusTopic.model_validate(t) for t in old]
    new_topics = [SyllabusTopic.model_validate(t) for t in new]
    old_flat = _flatten(old_topics)
    new_flat = _flatten(new_topics)
    added = sorted(set(new_flat) - set(old_flat))
    removed = sorted(set(old_flat) - set(new_flat))
    renamed: list[tuple[str, str]] = []
    for tid in set(old_flat) & set(new_flat):
        if old_flat[tid].title != new_flat[tid].title:
            renamed.append((old_flat[tid].title, new_flat[tid].title))
    return DiffSyllabusOutput(added=added, removed=removed, renamed=renamed).model_dump()


def main() -> None:
    """stdio entry point."""
    mcp_server.run()


if __name__ == "__main__":
    main()
