"""Insight agent: historical exam stats with parallel fan-out.

Pattern: **parallelisation**. The three views (cutoffs / selection % /
heatmap) are independent fetches, so we fire them concurrently with
``asyncio.gather`` and join the results. The Insight panel makes no
factual claim that isn't tagged with a ``source``; the agent re-checks
that invariant before returning.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from api.mcp import MCPClient, MCPServerSpec


def default_stats_spec() -> MCPServerSpec:
    return MCPServerSpec(command="python", args=["-m", "mcp_stats.server"], env=os.environ.copy())


@dataclass(slots=True)
class InsightPanel:
    exam_id: str
    cutoffs: list[dict[str, Any]] = field(default_factory=list)
    selection_pct: list[dict[str, Any]] = field(default_factory=list)
    heatmap: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MissingProvenanceError(RuntimeError):
    """Raised when any cutoff / selection-pct row arrives without a source."""


class InsightAgent:
    def __init__(self, client: MCPClient | None = None) -> None:
        self._client = client or MCPClient(default_stats_spec())

    async def panel(self, exam_id: str, *, last_n_years: int = 5) -> InsightPanel:
        cutoffs_t, selection_t, heatmap_t = await asyncio.gather(
            self._client.call("cutoffs", {"exam_id": exam_id, "last_n_years": last_n_years}),
            self._client.call("selection_pct", {"exam_id": exam_id, "last_n_years": last_n_years}),
            self._client.call("topic_heatmap", {"exam_id": exam_id}),
        )

        cutoffs = _rows(cutoffs_t)
        selection = _rows(selection_t)
        heatmap_items = list((heatmap_t or {}).get("items") or [])
        heatmap_source = (heatmap_t or {}).get("source", "")

        sources: list[str] = []
        for row in cutoffs:
            source = (row or {}).get("source")
            if not source:
                raise MissingProvenanceError(f"cutoff row without source: {row!r}")
            sources.append(str(source))
        for row in selection:
            source = (row or {}).get("source")
            if not source:
                raise MissingProvenanceError(f"selection_pct row without source: {row!r}")
            sources.append(str(source))
        if heatmap_source:
            sources.append(str(heatmap_source))

        # De-dup, keep order.
        seen: set[str] = set()
        unique_sources: list[str] = []
        for s in sources:
            if s not in seen:
                seen.add(s)
                unique_sources.append(s)

        return InsightPanel(
            exam_id=exam_id,
            cutoffs=cutoffs,
            selection_pct=selection,
            heatmap=heatmap_items,
            sources=unique_sources,
        )


def _rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]
