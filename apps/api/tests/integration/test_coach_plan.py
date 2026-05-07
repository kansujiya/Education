"""M-5 demo lock-in: Onboarding → Coach plan → replan on signal.

Plans are deterministic (the planning core is a pure function), so we
test against fixed PYQ frequencies and progress maps.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from api.agents.coach import CoachAgent
from api.agents.onboarding import OnboardingAgent
from api.db import models as orm
from api.db.repositories import (
    ExamRepo,
    PlanRepo,
    ProfileRepo,
    ProgressRepo,
    SyllabusRepo,
)
from api.listeners import dispatch_event, set_pyq_frequency_provider
from fakeredis import aioredis as fake_aioredis
from shared.events import PlanReplan
from shared.models import SyllabusTopic


@pytest.fixture
def fake_redis():
    return fake_aioredis.FakeRedis(decode_responses=True)


async def _seed_aws_ccp(db) -> None:
    """A trimmed exam tree: 4 leaf topics with distinct PYQ weights."""
    await ExamRepo(db).upsert("aws-ccp", "AWS CCP", "aws-ccp")
    tree = [
        SyllabusTopic(id="t.high", exam_id="aws-ccp", title="High yield"),
        SyllabusTopic(id="t.mid", exam_id="aws-ccp", title="Medium yield"),
        SyllabusTopic(id="t.low", exam_id="aws-ccp", title="Low yield"),
        SyllabusTopic(id="t.nopyq", exam_id="aws-ccp", title="No PYQ history"),
    ]
    await SyllabusRepo(db).replace_for_exam("aws-ccp", tree)
    await db.flush()


@pytest.mark.asyncio
async def test_onboarding_persists_profile_and_emits_event(db, fake_redis) -> None:
    await _seed_aws_ccp(db)
    agent = OnboardingAgent()
    result = await agent.run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=60),
        daily_minutes=60,
        redis=fake_redis,
    )
    assert result.profile.exam_id == "aws-ccp"
    assert result.profile.daily_minutes == 60

    profile = await ProfileRepo(db, "u_a").get()
    assert profile is not None
    assert profile.exam_id == "aws-ccp"

    entries = await fake_redis.xread({"education:events": 0})
    payloads = [pair[1]["data"] for pair in entries[0][1]]
    assert any("user.onboarded" in p for p in payloads)


@pytest.mark.asyncio
async def test_plan_orders_by_pyq_weight(db) -> None:
    await _seed_aws_ccp(db)
    await OnboardingAgent().run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=14),
        daily_minutes=60,
    )
    pyq = {"t.high": 5, "t.mid": 3, "t.low": 1, "t.nopyq": 0}

    coach = CoachAgent()
    result = await coach.plan(db, user_id="u_a", pyq_frequency=pyq, days_window=2)

    days = result.plan.days
    assert days, "expected at least one day"
    # daily_minutes=60, default minutes_per_topic=30 → 2 topics/day.
    flat_topics = [t.topic_id for d in days for t in d.topics]
    # Highest-yield topics must come first overall.
    assert flat_topics[0] == "t.high"
    assert flat_topics[1] == "t.mid"
    # Across days: day 1 carries the two heaviest topics.
    day1_ids = {t.topic_id for t in days[0].topics}
    assert day1_ids == {"t.high", "t.mid"}


@pytest.mark.asyncio
async def test_replan_drops_mastered_topics(db) -> None:
    """After bumping mastery on the heaviest topic, replan must surface
    the next topic in its place — same Coach API, different output."""
    await _seed_aws_ccp(db)
    await OnboardingAgent().run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=14),
        daily_minutes=30,
    )
    pyq = {"t.high": 5, "t.mid": 3, "t.low": 1, "t.nopyq": 0}
    coach = CoachAgent()

    first = await coach.plan(db, user_id="u_a", pyq_frequency=pyq, days_window=1)
    assert first.plan.days[0].topics[0].topic_id == "t.high"

    # Mark high-yield topic mastered → its score drops to ~0.
    await ProgressRepo(db, "u_a").upsert("t.high", mastery=1.0)
    await db.commit()
    second = await coach.plan(db, user_id="u_a", pyq_frequency=pyq, days_window=1)

    assert second.plan.days[0].topics[0].topic_id != "t.high"
    assert second.plan.days[0].topics[0].topic_id in {"t.mid", "t.low", "t.nopyq"}


@pytest.mark.asyncio
async def test_plan_persisted_via_repo(db) -> None:
    await _seed_aws_ccp(db)
    await OnboardingAgent().run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=14),
        daily_minutes=60,
    )
    coach = CoachAgent()
    await coach.plan(
        db,
        user_id="u_a",
        pyq_frequency={"t.high": 5, "t.mid": 3, "t.low": 1, "t.nopyq": 0},
    )
    await db.commit()
    latest = await PlanRepo(db, "u_a").latest()
    assert latest is not None
    assert latest.user_id == "u_a"


@pytest.mark.asyncio
async def test_replan_listener_writes_new_plan(db, fake_redis) -> None:
    """Firing plan.replan with a frequency provider wired produces a new plan row."""
    await _seed_aws_ccp(db)
    await OnboardingAgent().run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=14),
        daily_minutes=60,
    )
    await db.commit()

    pyq = {"t.high": 5, "t.mid": 3, "t.low": 1, "t.nopyq": 0}

    async def provider() -> dict[str, int]:
        return pyq

    set_pyq_frequency_provider(provider)
    try:
        event = PlanReplan(user_id="u_a", reason="test")
        await dispatch_event(event, db=db, redis=fake_redis)
        await db.commit()
    finally:
        set_pyq_frequency_provider(None)

    rows = (await db.execute(orm.Plan.__table__.select().where(orm.Plan.user_id == "u_a"))).all()
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_replan_listener_noop_without_provider(db, fake_redis) -> None:
    """When no provider is wired, the listener is a no-op (does not raise)."""
    await _seed_aws_ccp(db)
    await OnboardingAgent().run(
        db,
        user_id="u_a",
        email="a@x.com",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=14),
        daily_minutes=60,
    )
    await db.commit()
    set_pyq_frequency_provider(None)

    event = PlanReplan(user_id="u_a", reason="test")
    await dispatch_event(event, db=db, redis=fake_redis)
    # No exception, nothing crashes; listener silently skipped.
