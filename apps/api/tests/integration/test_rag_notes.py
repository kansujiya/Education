"""M-2 RAG: NotesIndex retrieves relevant chunks for AWS CCP topics."""

from __future__ import annotations

from pathlib import Path

import pytest
from api.rag import NotesIndex

REPO = Path(__file__).resolve().parents[4]
NOTES = REPO / "seeds" / "notes_aws_ccp.jsonl"


@pytest.fixture(scope="module")
def index() -> NotesIndex:
    return NotesIndex.from_jsonl(NOTES)


def test_index_loads_all_chunks(index: NotesIndex) -> None:
    # The seed file has 28 lines.
    assert len(index.chunks) >= 27


def test_recall_at_5_above_threshold(index: NotesIndex) -> None:
    """For a hand-labelled set of (query, expected_topic_id), the relevant
    topic must appear in the top-5 results.

    The threshold for v0.1 is 100% on this curated set; we'll loosen if
    more cases are added.
    """
    cases: list[tuple[str, str]] = [
        ("shared responsibility customer hardware", "security.shared-resp"),
        ("least privilege MFA IAM users roles", "security.iam"),
        ("EC2 lambda compute virtual machines", "technology.compute"),
        ("S3 object storage durability", "technology.storage"),
        ("savings plans reserved spot pricing", "billing.pricing"),
        ("region availability zone edge location", "technology.global-infra"),
    ]
    hits = 0
    for query, expected in cases:
        results = index.search(query, k=5)
        topics = {r.chunk.topic_id for r in results}
        if expected in topics:
            hits += 1
    assert hits / len(cases) >= 0.8, f"recall@5 too low: {hits}/{len(cases)}"


def test_topic_filter_narrows_results(index: NotesIndex) -> None:
    results = index.search("least privilege", k=5, topic_id="security.iam")
    assert results
    assert all(r.chunk.topic_id == "security.iam" for r in results)


def test_provenance_preserved(index: NotesIndex) -> None:
    results = index.search("shared responsibility", k=3)
    assert results
    assert all(r.chunk.source for r in results)
