"""MCP server exposing past-year-question (PYQ) tools.

For v0.1 the corpus is a JSONL file shipped under ``seeds/``. The same
TF cosine retriever from ``api.rag.notes`` would work but the dependency
direction is wrong (an MCP server can't import the API). We re-implement
a tiny retriever inline so this server stays a leaf in the graph.

Run via:
    python -m mcp_pyq.server
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]+\b")


def _data_path() -> Path:
    base = Path(os.environ.get("MCP_PYQ_DATA_DIR", "seeds")).resolve()
    return base / "pyqs_aws_ccp.jsonl"


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass(slots=True)
class _PYQ:
    id: str
    topic_id: str
    year: int
    section: str
    stem: str
    model_answer: str
    key_points: list[str]


@lru_cache(maxsize=1)
def _load() -> list[_PYQ]:
    path = _data_path()
    items: list[_PYQ] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        items.append(
            _PYQ(
                id=d["id"],
                topic_id=d["topic_id"],
                year=int(d["year"]),
                section=d.get("section", ""),
                stem=d["stem"],
                model_answer=d.get("model_answer", ""),
                key_points=list(d.get("key_points", [])),
            )
        )
    return items


def _by_id(pyq_id: str) -> _PYQ | None:
    for p in _load():
        if p.id == pyq_id:
            return p
    return None


def _vocab(items: Iterable[_PYQ]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in items:
        text = f"{p.stem} {p.model_answer} {' '.join(p.key_points)}"
        for tok in _tokenize(text):
            if tok not in out:
                out[tok] = len(out)
    return out


def _vectorise(text: str, vocab: dict[str, int]) -> list[float]:
    counts = Counter(_tokenize(text))
    vec = [0.0] * len(vocab)
    for tok, n in counts.items():
        i = vocab.get(tok)
        if i is not None:
            vec[i] = float(n)
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def _to_dict(p: _PYQ, *, score: float | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": p.id,
        "topic_id": p.topic_id,
        "year": p.year,
        "section": p.section,
        "stem": p.stem,
        "model_answer": p.model_answer,
        "key_points": list(p.key_points),
    }
    if score is not None:
        out["score"] = round(score, 4)
    return out


# ---- Server tools ----------------------------------------------------

mcp_server = FastMCP("pyq")


@mcp_server.tool()
def search_pyq(query: str, k: int = 5, topic_id: str | None = None) -> dict[str, Any]:
    """Top-k PYQs by cosine similarity with optional topic filter."""
    items = _load()
    if topic_id is not None:
        items = [p for p in items if p.topic_id == topic_id]
    if not items:
        return {"results": []}
    vocab = _vocab(items)
    q_vec = _vectorise(query, vocab)
    scored = [(p, _cosine(q_vec, _vectorise(p.stem + " " + p.model_answer, vocab))) for p in items]
    scored.sort(key=lambda x: x[1], reverse=True)
    return {"results": [_to_dict(p, score=s) for p, s in scored[:k] if s > 0]}


@mcp_server.tool()
def get_pyq(pyq_id: str) -> dict[str, Any]:
    """Look up a single PYQ by id."""
    p = _by_id(pyq_id)
    if p is None:
        raise LookupError(f"unknown pyq_id={pyq_id!r}")
    return _to_dict(p)


@mcp_server.tool()
def pyq_frequency(window_years: int = 5) -> dict[str, Any]:
    """Per-topic count of PYQs over the last ``window_years`` years.

    The result tells the Coach which topics are 'high yield' for
    weighting the study plan.
    """
    items = _load()
    if not items:
        return {"counts": {}, "max_year": None, "min_year": None}
    max_year = max(p.year for p in items)
    cutoff = max_year - window_years + 1
    counts: dict[str, int] = {}
    for p in items:
        if p.year < cutoff:
            continue
        counts[p.topic_id] = counts.get(p.topic_id, 0) + 1
    return {
        "counts": counts,
        "max_year": max_year,
        "min_year": cutoff,
        "window_years": window_years,
    }


def main() -> None:
    mcp_server.run()


if __name__ == "__main__":
    main()
