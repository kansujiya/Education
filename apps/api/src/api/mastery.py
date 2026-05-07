"""Mastery: how well the user knows a topic.

Pure function over a sequence of card attempts. We weight recent
attempts more heavily so a user who just started getting answers right
moves up faster than the running average would suggest.
"""

from __future__ import annotations

from collections.abc import Iterable

from api.db import models as orm

MASTERY_THRESHOLD = 0.8


def compute_mastery(attempts: Iterable[orm.CardAttempt]) -> float:
    """Weighted mean of attempt scores; latest attempt has weight N, oldest 1.

    Returns 0.0 when there are no attempts.
    """
    items = list(attempts)
    if not items:
        return 0.0
    items.sort(key=lambda a: a.attempt_at)
    weighted_sum = 0.0
    weight_total = 0.0
    for i, a in enumerate(items, start=1):
        weighted_sum += a.score * i
        weight_total += i
    if weight_total == 0:
        return 0.0
    return round(weighted_sum / weight_total, 4)


def is_mastered(mastery: float) -> bool:
    return mastery >= MASTERY_THRESHOLD
