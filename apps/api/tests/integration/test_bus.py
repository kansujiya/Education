"""M-1 unit tests for the bus + session helpers (fake Redis)."""

from __future__ import annotations

import pytest
from api.bus.events import EVENTS_STREAM, emit_event
from api.bus.sessions import read_session, write_session
from fakeredis import aioredis as fake_aioredis
from shared.events import TopicUnderstood


@pytest.fixture
def fake_redis():
    return fake_aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_emit_event_lands_on_stream(fake_redis) -> None:
    event = TopicUnderstood(
        user_id="u_1",
        topic_id="cloud-concepts",
        score=0.9,
    )

    entry_id = await emit_event(event, redis=fake_redis)

    assert entry_id
    entries = await fake_redis.xread({EVENTS_STREAM: 0})
    assert entries
    _, payload_pairs = entries[0]
    assert len(payload_pairs) == 1
    _, fields = payload_pairs[0]
    assert "topic.understood" in fields["data"]
    assert "cloud-concepts" in fields["data"]


@pytest.mark.asyncio
async def test_emit_event_persists_audit_row(fake_redis, db) -> None:
    event = TopicUnderstood(user_id="u_1", topic_id="t1", score=1.0)
    await emit_event(event, redis=fake_redis, db=db)
    await db.commit()

    from api.db import models as orm
    from sqlalchemy import select

    rows = (await db.execute(select(orm.EventRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "topic.understood"
    assert rows[0].user_id == "u_1"


@pytest.mark.asyncio
async def test_session_round_trip(fake_redis) -> None:
    state = {"step": "teach", "topic": "cloud-concepts"}
    await write_session("u_1", "tutor", state, redis=fake_redis)
    got = await read_session("u_1", "tutor", redis=fake_redis)
    assert got == state


@pytest.mark.asyncio
async def test_session_returns_empty_when_unset(fake_redis) -> None:
    got = await read_session("u_99", "tutor", redis=fake_redis)
    assert got == {}


@pytest.mark.asyncio
async def test_session_isolated_per_user(fake_redis) -> None:
    await write_session("u_1", "tutor", {"x": 1}, redis=fake_redis)
    await write_session("u_2", "tutor", {"x": 2}, redis=fake_redis)
    assert (await read_session("u_1", "tutor", redis=fake_redis))["x"] == 1
    assert (await read_session("u_2", "tutor", redis=fake_redis))["x"] == 2
