"""Listener registry + dispatcher.

Listeners are async functions:
    async def handler(event: Event, *, db: AsyncSession, redis: Redis) -> None

They register against an ``EventName``. ``dispatch_event`` runs all
registered handlers for the event's name. The CLI (and later the
worker process) calls ``dispatch_event`` after ``emit_event``.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from redis.asyncio import Redis
from shared.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

Listener = Callable[..., Coroutine[Any, Any, None]]

REGISTRY: dict[str, list[Listener]] = {}


def register(event_name: str, handler: Listener) -> None:
    REGISTRY.setdefault(event_name, []).append(handler)


async def dispatch_event(
    event: Event,
    *,
    db: AsyncSession,
    redis: Redis,
) -> None:
    handlers = REGISTRY.get(event.name, [])
    for handler in handlers:
        await handler(event, db=db, redis=redis)
