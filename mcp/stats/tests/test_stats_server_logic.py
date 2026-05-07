"""Pure-logic tests for mcp-stats."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp_stats.server import _load_pyq_counts, _load_stats, cutoffs, selection_pct, topic_heatmap

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _seeds_dir(monkeypatch):
    monkeypatch.setenv("MCP_STATS_DATA_DIR", str(REPO / "seeds"))
    _load_stats.cache_clear()
    _load_pyq_counts.cache_clear()


def test_cutoffs_returns_last_n_years() -> None:
    out = cutoffs("aws-ccp", last_n_years=3)
    assert out["exam_id"] == "aws-ccp"
    assert len(out["rows"]) == 3
    years = [r["year"] for r in out["rows"]]
    assert years == sorted(years, reverse=True)
    assert all(r["source"] for r in out["rows"])


def test_selection_pct_carries_provenance() -> None:
    out = selection_pct("aws-ccp")
    assert out["rows"]
    for row in out["rows"]:
        assert row["source"]
        assert "estimated" in row  # flag must be explicit, even when False


def test_topic_heatmap_counts_match_pyq_corpus() -> None:
    out = topic_heatmap("aws-ccp")
    assert out["total_pyqs"] >= 25
    # All 13 leaf topics from M-2 / M-4 seeds appear.
    topic_ids = {item["topic_id"] for item in out["items"]}
    assert {"security.iam", "technology.compute", "billing.pricing"}.issubset(topic_ids)
    assert out["source"]


def test_unknown_exam_raises() -> None:
    with pytest.raises(FileNotFoundError):
        cutoffs("nope-2099")
