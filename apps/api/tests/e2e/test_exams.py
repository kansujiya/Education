"""M-7: ``/v1/exams/*`` global endpoints."""

from __future__ import annotations

import os

import pytest


@pytest.mark.asyncio
async def test_list_exams(app_and_client) -> None:
    _, client = app_and_client
    r = await client.get("/v1/exams")
    assert r.status_code == 200
    ids = {e["id"] for e in r.json()["exams"]}
    assert "aws-ccp" in ids


@pytest.mark.asyncio
async def test_syllabus_returns_topic_tree(app_and_client) -> None:
    _, client = app_and_client
    r = await client.get("/v1/exams/aws-ccp/syllabus")
    assert r.status_code == 200
    body = r.json()
    titles = [t["title"] for t in body["topics"]]
    assert "Benefits of the Cloud" in titles


@pytest.mark.asyncio
async def test_unknown_exam_404(app_and_client) -> None:
    _, client = app_and_client
    r = await client.get("/v1/exams/no-such/syllabus")
    assert r.status_code == 404


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_insights_endpoint_returns_provenance(app_and_client, monkeypatch) -> None:
    """Spawns mcp-stats to verify the panel really fans out — the slowest
    e2e test, but it locks the wiring."""
    from pathlib import Path

    monkeypatch.setenv("MCP_STATS_DATA_DIR", str(Path(__file__).resolve().parents[4] / "seeds"))
    _, client = app_and_client
    # Forward any env we set above to subprocess spawning.
    os.environ["MCP_STATS_DATA_DIR"] = os.environ["MCP_STATS_DATA_DIR"]

    r = await client.get("/v1/exams/aws-ccp/insights?last_n_years=3")
    assert r.status_code == 200
    body = r.json()
    assert body["cutoffs"]
    assert body["selection_pct"]
    assert body["sources"]
    for row in body["cutoffs"]:
        assert row["source"]
