"""M-4: SM-2 schedule + mastery formula are pure-function correct."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

from api.db import models as orm
from api.mastery import compute_mastery, is_mastered
from api.sr import SUCCESS_INTERVALS_DAYS, interval_days, next_due_at


def test_interval_grows_with_correct_streak() -> None:
    intervals = [interval_days(score=1.0, prior_correct=i) for i in range(7)]
    assert intervals[0] == SUCCESS_INTERVALS_DAYS[0]
    # Monotonically non-decreasing — the series caps at the last value.
    assert all(b >= a for a, b in pairwise(intervals))
    assert intervals[-1] == SUCCESS_INTERVALS_DAYS[-1]


def test_failed_attempt_resets_to_one_day() -> None:
    assert interval_days(score=0.5, prior_correct=10) == 1


def test_next_due_at_uses_now() -> None:
    now = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    due = next_due_at(score=1.0, prior_correct=0, now=now)
    assert due > now
    assert (due - now).days == SUCCESS_INTERVALS_DAYS[0]


def _att(score: float, when: datetime) -> orm.CardAttempt:
    return orm.CardAttempt(
        id="x",
        card_id="c",
        user_id="u",
        attempt_at=when,
        score=score,
        due_at=None,
    )


def test_mastery_zero_with_no_attempts() -> None:
    assert compute_mastery([]) == 0.0


def test_mastery_recent_weighted_more() -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    attempts = [
        _att(0.0, base.replace(day=1)),
        _att(0.5, base.replace(day=2)),
        _att(1.0, base.replace(day=3)),
    ]
    # Latest attempt has weight 3, oldest 1: (0*1 + 0.5*2 + 1*3)/6 ≈ 0.667
    assert compute_mastery(attempts) > sum(a.score for a in attempts) / len(attempts) - 1e-6
    assert compute_mastery(attempts) > 0.65


def test_is_mastered_threshold() -> None:
    assert is_mastered(0.81)
    assert not is_mastered(0.79)
