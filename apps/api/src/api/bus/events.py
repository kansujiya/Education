"""Emit events to Redis Streams + persist an audit row.

Event objects are versioned Pydantic models in ``shared.events``. Emitting
writes the JSON envelope to the stream and (when a DB session is given)
appends to the ``events`` audit table.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

from redis.asyncio import Redis
from shared.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db import models as orm

EVENTS_STREAM = "education:events"


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def reset_redis_cache() -> None:
    """Drop cached Redis client; tests use this to inject fakes."""
    get_redis.cache_clear()


async def emit_event(
    event: Event,
    *,
    redis: Redis | None = None,
    db: AsyncSession | None = None,
) -> str:
    """Emit ``event`` on the Redis stream; optionally also persist audit row.

    Returns the Redis Streams entry id so callers (including tests) can
    read the entry back.
    """
    client = redis or get_redis()
    payload: dict[str, Any] = event.model_dump(mode="json")
    entry_id = await client.xadd(EVENTS_STREAM, {"data": _to_json(payload)})

    if db is not None:
        db.add(
            orm.EventRow(
                id=event.id,
                name=event.name,
                user_id=event.user_id,
                payload=payload,
            )
        )
        await db.flush()

    return cast(str, entry_id)


def _to_json(obj: Any) -> str:
    import json as _json

    return _json.dumps(obj, separators=(",", ":"), default=str)
