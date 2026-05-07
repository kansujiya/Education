"""progress_updater: recompute mastery + emit topic.mastered when threshold crossed.

Subscribed to ``card.attempted``.
"""

from __future__ import annotations

from redis.asyncio import Redis
from shared.events import CardAttempted, Event, TopicMastered
from sqlalchemy.ext.asyncio import AsyncSession

from api.bus.events import emit_event
from api.db.repositories import CardAttemptRepo, CardRepo, ProgressRepo
from api.listeners.dispatcher import register
from api.mastery import compute_mastery, is_mastered


async def progress_updater(
    event: Event,
    *,
    db: AsyncSession,
    redis: Redis,
) -> None:
    if not isinstance(event, CardAttempted):
        return
    user_id = event.user_id or ""
    if not user_id:
        return  # nothing to scope to

    cards = CardRepo(db, user_id)
    attempts = CardAttemptRepo(db, user_id)
    progress_repo = ProgressRepo(db, user_id)

    card = await cards.get(event.card_id)
    if card is None:
        return

    topic_attempts = await attempts.list_for_topic(card.topic_id)
    mastery = compute_mastery(topic_attempts)
    progress = await progress_repo.upsert(card.topic_id, mastery=mastery)
    await db.commit()

    if is_mastered(progress.mastery):
        await emit_event(
            TopicMastered(
                user_id=user_id,
                topic_id=card.topic_id,
                mastery=progress.mastery,
            ),
            redis=redis,
            db=db,
        )
        await db.commit()


register("card.attempted", progress_updater)
