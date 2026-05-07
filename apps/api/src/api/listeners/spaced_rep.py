"""spaced_rep_scheduler: stamp ``due_at`` on the latest card_attempt row.

Subscribed to ``card.attempted``. The attempt row was inserted by the
producer (the CLI / API endpoint); this listener loads it back, counts
prior correct attempts on the same card, and updates ``due_at``.
"""

from __future__ import annotations

from redis.asyncio import Redis
from shared.events import CardAttempted, Event
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import models as orm
from api.listeners.dispatcher import register
from api.sr import PASS_THRESHOLD, next_due_at


async def spaced_rep_scheduler(
    event: Event,
    *,
    db: AsyncSession,
    redis: Redis,
) -> None:
    if not isinstance(event, CardAttempted):
        return
    user_id = event.user_id or ""
    if not user_id:
        return

    # Find the most recent attempt for (user, card). The producer inserted
    # this row before emitting; we mutate its due_at.
    latest = (
        await db.execute(
            select(orm.CardAttempt)
            .where(
                orm.CardAttempt.user_id == user_id,
                orm.CardAttempt.card_id == event.card_id,
            )
            .order_by(desc(orm.CardAttempt.attempt_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return

    prior_correct = (
        (
            await db.execute(
                select(orm.CardAttempt).where(
                    orm.CardAttempt.user_id == user_id,
                    orm.CardAttempt.card_id == event.card_id,
                    orm.CardAttempt.id != latest.id,
                    orm.CardAttempt.score >= PASS_THRESHOLD,
                )
            )
        )
        .scalars()
        .all()
    )

    latest.due_at = next_due_at(score=event.score, prior_correct=len(prior_correct))
    await db.commit()


register("card.attempted", spaced_rep_scheduler)
