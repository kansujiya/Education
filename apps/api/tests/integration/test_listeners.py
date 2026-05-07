"""M-4 demo lock-in: progress_updater + spaced_rep_scheduler.

The producer (CLI / API) inserts the CardAttempt row, then emits
``card.attempted``. We assert the listeners do their work end-to-end:

  - progress_updater recomputes mastery and writes to ``progress``.
  - spaced_rep_scheduler stamps ``due_at`` on the latest attempt.
  - When mastery crosses MASTERY_THRESHOLD, ``topic.mastered`` lands on
    the bus.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from api.bus.events import EVENTS_STREAM
from api.db import models as orm
from api.db.repositories import CardAttemptRepo, CardRepo, UserRepo
from api.listeners import dispatch_event
from api.listeners.progress import progress_updater
from api.listeners.spaced_rep import spaced_rep_scheduler
from fakeredis import aioredis as fake_aioredis
from shared.events import CardAttempted


@pytest.fixture
def fake_redis():
    return fake_aioredis.FakeRedis(decode_responses=True)


async def _seed_topic(db, user_id: str, topic_id: str = "cloud-concepts.benefits") -> None:
    db.add(orm.Exam(id="aws-ccp", name="AWS CCP", slug="aws-ccp"))
    db.add(orm.SyllabusTopic(id=topic_id, exam_id="aws-ccp", title="Topic", weight=1.0))
    await UserRepo(db).upsert(user_id, email=f"{user_id}@x.com")
    await db.flush()


async def _add_card(db, user_id: str, *, card_id: str, topic_id: str) -> orm.Card:
    cards = CardRepo(db, user_id)
    [row] = await cards.add_many(
        [
            {
                "id": card_id,
                "topic_id": topic_id,
                "type": "recall",
                "prompt": "what?",
                "answer": "thing",
                "key_points": ["thing"],
            }
        ]
    )
    return row


@pytest.mark.asyncio
async def test_progress_updater_recomputes_mastery(db, fake_redis) -> None:
    await _seed_topic(db, "u_a")
    await _add_card(db, "u_a", card_id="c1", topic_id="cloud-concepts.benefits")
    # One attempt for the card at score 0.9.
    await CardAttemptRepo(db, "u_a").add(card_id="c1", score=0.9)
    await db.commit()

    event = CardAttempted(
        user_id="u_a", card_id="c1", topic_id="cloud-concepts.benefits", score=0.9, correct=True
    )
    await progress_updater(event, db=db, redis=fake_redis)

    progress = await db.get(orm.Progress, ("u_a", "cloud-concepts.benefits"))
    assert progress is not None
    assert progress.mastery == 0.9


@pytest.mark.asyncio
async def test_spaced_rep_scheduler_sets_due_at(db, fake_redis) -> None:
    await _seed_topic(db, "u_a")
    await _add_card(db, "u_a", card_id="c1", topic_id="cloud-concepts.benefits")
    # One earlier correct attempt + a fresh one (the producer just added).
    earlier = datetime(2026, 5, 1, tzinfo=UTC)
    await CardAttemptRepo(db, "u_a").add(card_id="c1", score=1.0, attempt_at=earlier)
    new_attempt = await CardAttemptRepo(db, "u_a").add(card_id="c1", score=1.0)
    assert new_attempt.due_at is None
    await db.commit()

    event = CardAttempted(
        user_id="u_a", card_id="c1", topic_id="cloud-concepts.benefits", score=1.0, correct=True
    )
    await spaced_rep_scheduler(event, db=db, redis=fake_redis)

    await db.refresh(new_attempt)
    assert new_attempt.due_at is not None
    # 1 prior correct → next interval = 3 days (SUCCESS_INTERVALS_DAYS[1]).
    delta = (new_attempt.due_at - new_attempt.attempt_at).days
    assert delta == 3


@pytest.mark.asyncio
async def test_topic_mastered_fires_at_threshold(db, fake_redis) -> None:
    await _seed_topic(db, "u_a")
    await _add_card(db, "u_a", card_id="c1", topic_id="cloud-concepts.benefits")
    # 3 strong attempts → weighted mastery climbs above 0.8.
    for s in (0.9, 0.95, 1.0):
        await CardAttemptRepo(db, "u_a").add(card_id="c1", score=s)
    await db.commit()

    event = CardAttempted(
        user_id="u_a", card_id="c1", topic_id="cloud-concepts.benefits", score=1.0, correct=True
    )
    await dispatch_event(event, db=db, redis=fake_redis)

    entries = await fake_redis.xread({EVENTS_STREAM: 0})
    payloads = [pair[1]["data"] for pair in entries[0][1]]
    assert any("topic.mastered" in p for p in payloads)


@pytest.mark.asyncio
async def test_topic_mastered_does_not_fire_below_threshold(db, fake_redis) -> None:
    await _seed_topic(db, "u_a")
    await _add_card(db, "u_a", card_id="c1", topic_id="cloud-concepts.benefits")
    await CardAttemptRepo(db, "u_a").add(card_id="c1", score=0.4)
    await db.commit()

    event = CardAttempted(
        user_id="u_a", card_id="c1", topic_id="cloud-concepts.benefits", score=0.4, correct=False
    )
    await dispatch_event(event, db=db, redis=fake_redis)

    entries = await fake_redis.xread({EVENTS_STREAM: 0}) or []
    payloads = [pair[1]["data"] for pair in entries[0][1]] if entries else []
    assert not any("topic.mastered" in p for p in payloads)


@pytest.mark.asyncio
async def test_listener_isolation_across_users(db, fake_redis) -> None:
    """A's attempt must never write into B's progress row."""
    await _seed_topic(db, "u_a")
    await UserRepo(db).upsert("u_b", email="b@x.com")
    await _add_card(db, "u_a", card_id="c_a", topic_id="cloud-concepts.benefits")
    await _add_card(db, "u_b", card_id="c_b", topic_id="cloud-concepts.benefits")
    await CardAttemptRepo(db, "u_a").add(card_id="c_a", score=1.0)
    await db.commit()

    event = CardAttempted(
        user_id="u_a", card_id="c_a", topic_id="cloud-concepts.benefits", score=1.0, correct=True
    )
    await progress_updater(event, db=db, redis=fake_redis)

    a_progress = await db.get(orm.Progress, ("u_a", "cloud-concepts.benefits"))
    b_progress = await db.get(orm.Progress, ("u_b", "cloud-concepts.benefits"))
    assert a_progress is not None
    assert b_progress is None
