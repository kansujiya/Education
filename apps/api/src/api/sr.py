"""Spaced-repetition scheduling.

A pragmatic SM-2-flavour scheduler. Given:
  - the count of *prior* successful (correct) attempts for the card,
  - the score of the latest attempt (0.0 - 1.0),

return the interval (in days) until the card is shown again.

Rules:
  - score < 0.7 → reset; due tomorrow.
  - score ≥ 0.7 → grow interval geometrically: 1, 3, 7, 14, 30, 60 days.
    The series caps at ``MAX_INTERVAL_DAYS``.

Pure function so listeners and the CLI can both reuse it without
touching the DB or Redis.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# 0 prior correct → 1 day, 1 → 3, 2 → 7, 3 → 14, 4 → 30, 5+ → 60.
SUCCESS_INTERVALS_DAYS: tuple[int, ...] = (1, 3, 7, 14, 30, 60)
MAX_INTERVAL_DAYS = SUCCESS_INTERVALS_DAYS[-1]
PASS_THRESHOLD = 0.7


def next_due_at(
    *,
    score: float,
    prior_correct: int,
    now: datetime | None = None,
) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(days=interval_days(score=score, prior_correct=prior_correct))


def interval_days(*, score: float, prior_correct: int) -> int:
    if score < PASS_THRESHOLD:
        return 1  # reset on miss
    idx = min(prior_correct, len(SUCCESS_INTERVALS_DAYS) - 1)
    return SUCCESS_INTERVALS_DAYS[idx]
