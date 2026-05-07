"""Pure-logic tests for mcp-pyq."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp_pyq.server import _load, get_pyq, pyq_frequency, search_pyq

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _seeds_dir(monkeypatch):
    monkeypatch.setenv("MCP_PYQ_DATA_DIR", str(REPO / "seeds"))
    _load.cache_clear()


def test_corpus_loads() -> None:
    rows = _load()
    assert len(rows) >= 25
    assert all(r.year >= 2000 for r in rows)


def test_search_returns_relevant_pyqs() -> None:
    out = search_pyq("least privilege MFA", k=5)
    topics = {r["topic_id"] for r in out["results"]}
    assert "security.iam" in topics


def test_topic_filter_narrows_results() -> None:
    out = search_pyq("storage", k=5, topic_id="technology.storage")
    assert all(r["topic_id"] == "technology.storage" for r in out["results"])


def test_get_pyq_returns_full_record() -> None:
    out = get_pyq("pyq_001")
    assert out["id"] == "pyq_001"
    assert out["year"]
    assert out["model_answer"]
    assert out["key_points"]


def test_get_pyq_unknown_raises() -> None:
    with pytest.raises(LookupError):
        get_pyq("nope_999")


def test_frequency_within_window() -> None:
    out = pyq_frequency(window_years=2)
    counts = out["counts"]
    # window ≥ 1 should produce some counts.
    assert sum(counts.values()) > 0
    assert out["max_year"] >= out["min_year"]
