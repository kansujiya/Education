"""MCP server exposing historical exam stats: cutoffs, selection %, heatmap.

Every number returned carries a ``source`` and (where applicable) an
``estimated`` flag so the UI can render provenance honestly. PYQ-frequency
heatmap is computed inline from ``seeds/pyqs_*.jsonl`` so we don't need
mcp-pyq running as well.

Run via:
    python -m mcp_stats.server
"""

from __future__ import annotations

import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _data_dir() -> Path:
    return Path(os.environ.get("MCP_STATS_DATA_DIR", "seeds")).resolve()


@lru_cache(maxsize=8)
def _load_stats(exam_id: str) -> dict[str, Any]:
    path = _data_dir() / f"stats_{exam_id.replace('-', '_')}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown exam_id={exam_id!r}; expected {path}")
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@lru_cache(maxsize=8)
def _load_pyq_counts(exam_id: str) -> dict[str, int]:
    """Count PYQs per topic across the seeded corpus."""
    path = _data_dir() / f"pyqs_{exam_id.replace('-', '_')}.jsonl"
    if not path.exists():
        return {}
    counter: Counter[str] = Counter()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        counter[d["topic_id"]] += 1
    return dict(counter)


# ---- Server tools ----------------------------------------------------

mcp_server = FastMCP("stats")


@mcp_server.tool()
def cutoffs(exam_id: str, last_n_years: int = 5) -> dict[str, Any]:
    """Return historical cutoff scores for the exam, capped at the last N years."""
    data = _load_stats(exam_id)
    rows = sorted(data.get("cutoffs", []), key=lambda r: r["year"], reverse=True)[:last_n_years]
    return {"exam_id": exam_id, "rows": rows}


@mcp_server.tool()
def selection_pct(exam_id: str, last_n_years: int = 5) -> dict[str, Any]:
    """Return historical selection percentages. Each row keeps its own
    ``source`` and ``estimated`` flag so the UI can label numbers."""
    data = _load_stats(exam_id)
    rows = sorted(data.get("selection_pct", []), key=lambda r: r["year"], reverse=True)[
        :last_n_years
    ]
    return {"exam_id": exam_id, "rows": rows}


@mcp_server.tool()
def topic_heatmap(exam_id: str) -> dict[str, Any]:
    """Per-topic PYQ counts. The 'heat' is the count itself; consumers
    normalise to colour later."""
    counts = _load_pyq_counts(exam_id)
    items = [{"topic_id": k, "pyq_count": v} for k, v in sorted(counts.items())]
    total = sum(counts.values())
    data = _load_stats(exam_id)
    return {
        "exam_id": exam_id,
        "items": items,
        "total_pyqs": total,
        "source": data.get(
            "heatmap_source",
            "Aggregated from seeded PYQs",
        ),
    }


def main() -> None:
    mcp_server.run()


if __name__ == "__main__":
    main()
