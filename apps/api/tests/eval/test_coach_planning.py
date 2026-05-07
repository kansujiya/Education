"""M-5 eval: pure-function plan invariants.

These do not call Anthropic — the planning core is deterministic. The
"eval" here is structural: every day's planned minutes must fit the
budget; mastery deprioritises topics; future windows shrink as the exam
approaches.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.planning import compute_plan
from shared.models import SyllabusTopic

TOPICS = [
    SyllabusTopic(id="t1", exam_id="aws-ccp", title="Topic 1"),
    SyllabusTopic(id="t2", exam_id="aws-ccp", title="Topic 2"),
    SyllabusTopic(id="t3", exam_id="aws-ccp", title="Topic 3"),
    SyllabusTopic(id="t4", exam_id="aws-ccp", title="Topic 4"),
    SyllabusTopic(id="t5", exam_id="aws-ccp", title="Topic 5"),
    SyllabusTopic(id="t6", exam_id="aws-ccp", title="Topic 6"),
    SyllabusTopic(id="t7", exam_id="aws-ccp", title="Topic 7"),
    SyllabusTopic(id="t8", exam_id="aws-ccp", title="Topic 8"),
]
EXAM_DATE = datetime.now(UTC) + timedelta(days=30)


def test_plan_fits_daily_budget_60() -> None:
    plan = compute_plan(
        user_id="u",
        exam_id="aws-ccp",
        exam_date=EXAM_DATE,
        daily_minutes=60,
        topics=TOPICS,
        pyq_frequency={t.id: 1 for t in TOPICS},
        progress={},
    )
    for day in plan.days:
        spent = sum(t.minutes for t in day.topics)
        assert spent <= 60, f"day {day.date} planned {spent} > budget 60"


def test_plan_fits_daily_budget_30() -> None:
    plan = compute_plan(
        user_id="u",
        exam_id="aws-ccp",
        exam_date=EXAM_DATE,
        daily_minutes=30,
        topics=TOPICS,
        pyq_frequency={t.id: 1 for t in TOPICS},
        progress={},
    )
    for day in plan.days:
        spent = sum(t.minutes for t in day.topics)
        assert spent <= 30
        assert len(day.topics) <= 1


def test_window_shrinks_when_exam_close() -> None:
    plan = compute_plan(
        user_id="u",
        exam_id="aws-ccp",
        exam_date=datetime.now(UTC) + timedelta(days=2),
        daily_minutes=60,
        topics=TOPICS,
        pyq_frequency={t.id: 1 for t in TOPICS},
        progress={},
        days_window=7,
    )
    # Only ~2 days available, so the plan caps at 2 days.
    assert len(plan.days) <= 2


def test_zero_pyq_topics_still_appear() -> None:
    """Topics with no PYQ history still get the +0.5 floor and can land
    in the plan when the heavy topics fill earlier slots."""
    plan = compute_plan(
        user_id="u",
        exam_id="aws-ccp",
        exam_date=EXAM_DATE,
        daily_minutes=60,
        topics=TOPICS,
        pyq_frequency={"t1": 5},  # only t1 has PYQ history
        progress={},
        days_window=7,
    )
    flat = {t.topic_id for d in plan.days for t in d.topics}
    # t1 appears (heavy yield) plus several +0.5-floor topics.
    assert "t1" in flat
    assert len(flat) >= 4


def test_round_trip_serialisation() -> None:
    from api.planning import StudyPlan

    plan = compute_plan(
        user_id="u",
        exam_id="aws-ccp",
        exam_date=EXAM_DATE,
        daily_minutes=60,
        topics=TOPICS,
        pyq_frequency={t.id: 1 for t in TOPICS},
        progress={},
    )
    blob = plan.to_dict()
    rebuilt = StudyPlan.from_dict(blob)
    assert rebuilt.user_id == plan.user_id
    assert rebuilt.daily_minutes == plan.daily_minutes
    assert len(rebuilt.days) == len(plan.days)
    assert rebuilt.days[0].topics[0].topic_id == plan.days[0].topics[0].topic_id
