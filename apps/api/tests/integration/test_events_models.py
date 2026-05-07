"""M-1: event payload schemas round-trip cleanly via the discriminator."""

from __future__ import annotations

from shared.events import (
    CardAttempted,
    TopicUnderstood,
    UserOnboarded,
    parse_event,
)


def test_topic_understood_round_trip() -> None:
    e = TopicUnderstood(user_id="u_1", topic_id="t1", score=0.9)
    payload = e.model_dump(mode="json")
    parsed = parse_event(payload)
    assert isinstance(parsed, TopicUnderstood)
    assert parsed.score == 0.9
    assert parsed.topic_id == "t1"


def test_discriminator_picks_card_attempted() -> None:
    e = CardAttempted(
        user_id="u_2",
        card_id="c_42",
        topic_id="t1",
        score=1.0,
        correct=True,
    )
    parsed = parse_event(e.model_dump(mode="json"))
    assert isinstance(parsed, CardAttempted)
    assert parsed.correct is True


def test_user_onboarded_carries_metadata() -> None:
    e = UserOnboarded(user_id="u_3", exam_id="aws-ccp", daily_minutes=45)
    parsed = parse_event(e.model_dump(mode="json"))
    assert isinstance(parsed, UserOnboarded)
    assert parsed.daily_minutes == 45
    assert parsed.user_id == "u_3"
