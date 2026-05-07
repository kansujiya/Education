"""M-4 demo lock-in: mcp-pyq stdio round-trip returns ranked PYQs."""

from __future__ import annotations

import os

import pytest
from api.mcp import MCPClient, MCPServerSpec


@pytest.fixture
def pyq_spec() -> MCPServerSpec:
    return MCPServerSpec(
        command="python",
        args=["-m", "mcp_pyq.server"],
        env=os.environ.copy(),
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_search_pyq_round_trip(pyq_spec) -> None:
    out = await MCPClient(pyq_spec).call(
        "search_pyq", {"query": "MFA root user", "k": 5, "topic_id": "security.iam"}
    )
    assert isinstance(out, dict)
    results = out["results"]
    assert results, "expected at least one result"
    assert all(r["topic_id"] == "security.iam" for r in results)
    # Each PYQ comes back with year/section/key_points populated.
    assert all(r["year"] for r in results)
    assert all(r["key_points"] for r in results)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyq_frequency_round_trip(pyq_spec) -> None:
    out = await MCPClient(pyq_spec).call("pyq_frequency", {"window_years": 5})
    assert isinstance(out, dict)
    counts = out["counts"]
    assert counts, "expected non-empty counts"
    # Major topics from our seed corpus must appear.
    assert "security.iam" in counts
    assert sum(counts.values()) >= 10
