"""M-6 demo lock-in: InsightAgent + mcp-stats stdio round-trip.

Pure-logic checks of mcp-stats already live under ``mcp/stats/tests``.
This module asserts the agent-level invariant: **every cutoff and
selection-% number returned to the caller carries a source**, and the
parallel fan-out actually fans out (3 MCP calls).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from api.agents.insight import InsightAgent, MissingProvenanceError
from api.mcp import MCPClient, MCPServerSpec


@pytest.fixture
def stats_spec() -> MCPServerSpec:
    return MCPServerSpec(
        command="python",
        args=["-m", "mcp_stats.server"],
        env=os.environ.copy(),
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_insight_returns_provenance_for_every_number(stats_spec) -> None:
    panel = await InsightAgent(MCPClient(stats_spec)).panel("aws-ccp")
    assert panel.cutoffs, "expected cutoff rows"
    assert panel.selection_pct, "expected selection_pct rows"
    for row in panel.cutoffs:
        assert row.get("source"), f"cutoff missing source: {row}"
    for row in panel.selection_pct:
        assert row.get("source"), f"selection_pct missing source: {row}"
    # The agent collects unique sources for the UI.
    assert panel.sources
    assert len(panel.sources) == len(set(panel.sources))


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_insight_heatmap_includes_seeded_topics(stats_spec) -> None:
    panel = await InsightAgent(MCPClient(stats_spec)).panel("aws-ccp")
    topic_ids = {item["topic_id"] for item in panel.heatmap}
    assert {"security.iam", "technology.compute"}.issubset(topic_ids)


class _StubClient:
    """In-process stub of MCPClient — exercises the agent's parallelism."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.event = asyncio.Event()

    async def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, args))
        await asyncio.sleep(0)  # yield so all three start before any returns
        if tool == "cutoffs":
            return {"rows": [{"year": 2024, "cutoff_score": 700, "source": "blueprint"}]}
        if tool == "selection_pct":
            return {"rows": [{"year": 2024, "pct": 75.0, "source": "stats", "estimated": True}]}
        if tool == "topic_heatmap":
            return {"items": [{"topic_id": "x", "pyq_count": 1}], "source": "seeds"}
        return {}


@pytest.mark.asyncio
async def test_insight_calls_three_mcp_tools_in_parallel() -> None:
    stub = _StubClient()
    agent = InsightAgent(stub)  # type: ignore[arg-type]
    panel = await agent.panel("aws-ccp")

    tools_called = {name for name, _ in stub.calls}
    assert tools_called == {"cutoffs", "selection_pct", "topic_heatmap"}
    assert panel.cutoffs and panel.selection_pct and panel.heatmap


@pytest.mark.asyncio
async def test_insight_raises_when_source_missing() -> None:
    """If mcp-stats ever drops a ``source`` field, the agent fails fast."""

    class _NoProvenance:
        async def call(self, tool: str, _args: dict[str, Any]) -> dict[str, Any]:
            if tool == "cutoffs":
                return {"rows": [{"year": 2024, "cutoff_score": 700}]}  # no source!
            if tool == "selection_pct":
                return {"rows": []}
            return {"items": [], "source": "seeds"}

    with pytest.raises(MissingProvenanceError):
        await InsightAgent(_NoProvenance()).panel("aws-ccp")  # type: ignore[arg-type]
