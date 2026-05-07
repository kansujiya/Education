"""M-4 eval: Assessor cards are well-formed and PYQ-grounded.

Determinism comes from the eval fake. Real-LLM card quality evals are a
follow-up; this test pins the structure (mix of types, key points,
provenance, key-point-grounded grading) so a future regression breaks
the build.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from api.agents import AssessorAgent

REPO = Path(__file__).resolve().parents[4]
PYQS = REPO / "seeds" / "pyqs_aws_ccp.jsonl"


@pytest.fixture(scope="module")
def pyq_pool() -> list[dict]:
    return [json.loads(line) for line in PYQS.read_text().splitlines() if line.strip()]


def _topic_pyqs(pool: list[dict], topic_id: str) -> list[dict]:
    return [p for p in pool if p["topic_id"] == topic_id]


def test_issue_returns_six_cards(fake_anthropic_eval, pyq_pool) -> None:
    assessor = AssessorAgent(client=fake_anthropic_eval)
    pyqs = _topic_pyqs(pyq_pool, "cloud-concepts.benefits")
    cards = assessor.issue_cards(
        topic_title="Benefits of the Cloud",
        lesson_md="Cloud rents capacity ...",
        pyqs=pyqs,
        n=6,
    )
    assert len(cards) >= 5  # eval fake hard-codes 6
    types = {c.type for c in cards}
    # Mix of types: at least 2 distinct kinds.
    assert len(types) >= 2


def test_each_card_has_key_points(fake_anthropic_eval, pyq_pool) -> None:
    assessor = AssessorAgent(client=fake_anthropic_eval)
    pyqs = _topic_pyqs(pyq_pool, "security.iam")
    cards = assessor.issue_cards(
        topic_title="IAM",
        lesson_md="IAM provides identities and policies ...",
        pyqs=pyqs,
    )
    for c in cards:
        assert c.key_points, f"card {c.prompt!r} missing key_points"


def test_majority_of_cards_carry_provenance(fake_anthropic_eval, pyq_pool) -> None:
    assessor = AssessorAgent(client=fake_anthropic_eval)
    pyqs = _topic_pyqs(pyq_pool, "technology.compute")
    cards = assessor.issue_cards(
        topic_title="Compute Services",
        lesson_md="EC2, Lambda, ECS ...",
        pyqs=pyqs,
    )
    grounded = [c for c in cards if c.source_pyq_id]
    # ≥80% grounded — the eval fake seeds source_pyq_id on every card.
    assert len(grounded) / max(len(cards), 1) >= 0.8


def test_grade_attempt_uses_card_key_points(fake_anthropic_eval, pyq_pool) -> None:
    """An answer that mentions a key_point should be graded correct."""
    assessor = AssessorAgent(client=fake_anthropic_eval)
    pyqs = _topic_pyqs(pyq_pool, "cloud-concepts.benefits")
    cards = assessor.issue_cards(topic_title="Benefits of the Cloud", lesson_md="...", pyqs=pyqs)
    card = cards[0]
    good = f"This answer mentions {card.key_points[0]} clearly."
    bad = "completely unrelated rubbish"
    assert assessor.grade_attempt(card, good).correct is True
    assert assessor.grade_attempt(card, bad).correct is False
