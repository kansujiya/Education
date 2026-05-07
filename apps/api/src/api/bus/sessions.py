"""Session helpers used by agents to read/write working memory.

Sessions are namespaced by ``(user_id, agent_name)``. Storage is Redis
(JSON value). The DB ``sessions`` table is the durable mirror written
periodically; for hot read/write we go through Redis.
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from api.bus.events import get_redis


def _key(user_id: str, agent: str) -> str:
    if not user_id or not agent:
        raise ValueError("session key requires both user_id and agent")
    return f"sess:{user_id}:{agent}"


async def read_session(user_id: str, agent: str, *, redis: Redis | None = None) -> dict[str, Any]:
    client = redis or get_redis()
    raw = await client.get(_key(user_id, agent))
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return _safe_load(raw)


async def write_session(
    user_id: str,
    agent: str,
    state: dict[str, Any],
    *,
    redis: Redis | None = None,
    ttl_seconds: int | None = None,
) -> None:
    client = redis or get_redis()
    payload = json.dumps(state, separators=(",", ":"), default=str)
    if ttl_seconds:
        await client.set(_key(user_id, agent), payload, ex=ttl_seconds)
    else:
        await client.set(_key(user_id, agent), payload)


def _safe_load(raw: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
