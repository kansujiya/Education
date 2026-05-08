"""E2E fixtures: a fully wired FastAPI app talking to in-memory SQLite,
fakeredis, and the deterministic Anthropic eval-fake. No subprocesses,
no Docker, no Anthropic key.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api.bus.events import get_redis
from api.db.models import Base
from api.db.session import get_engine, get_session_factory
from api.storage import LocalStorage, set_storage
from api.web.app import build_app
from api.web.deps import get_db
from api.web.routers.me import get_llm_client
from fakeredis import aioredis as fake_aioredis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest_asyncio.fixture
async def app_and_client(
    tmp_path: Path,
    monkeypatch,
    fake_anthropic_eval,
) -> AsyncIterator[tuple[FastAPI, AsyncClient]]:
    """Spin up the app with all external state replaced by in-process fakes."""
    # 1. Database: in-memory SQLite, schema from ORM metadata.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("api.db.session.get_engine", lambda: engine)
    monkeypatch.setattr("api.db.session.get_session_factory", lambda: factory)
    # Reset cached singletons so the patches take.
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    # 2. Redis: fakeredis for both rate limit + bus. Patch every name
    # binding because some modules ``from ... import get_redis`` at
    # module-load time and won't see ``api.bus.events.get_redis`` mutate.
    fake = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("api.bus.events.get_redis", lambda: fake)
    monkeypatch.setattr("api.web.rate_limit.get_redis", lambda: fake)
    monkeypatch.setattr("api.web.deps.get_redis", lambda: fake)
    get_redis.cache_clear()

    # 3. Storage: tmp_path local filesystem.
    set_storage(LocalStorage(tmp_path / "artefacts"))

    # 4. JWT secret: deterministic.
    monkeypatch.setenv("JWT_SECRET", "test-secret-please-do-not-use")
    from api.config import settings as _settings

    _settings.jwt_secret = "test-secret-please-do-not-use"
    _settings.rate_limit_per_minute = 0  # disabled by default; one test re-enables

    # 5. App + LLM client override.
    app = build_app()

    fake_llm = fake_anthropic_eval

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _override_llm() -> Any:
        return fake_llm

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = _override_llm

    # 6. Optional: seed an Exam + topic so /v1/me endpoints have somewhere to land.
    async with factory() as session:
        from api.db import models as orm

        session.add(orm.Exam(id="aws-ccp", name="AWS CCP", slug="aws-ccp"))
        session.add(
            orm.SyllabusTopic(
                id="cloud-concepts.benefits",
                exam_id="aws-ccp",
                title="Benefits of the Cloud",
                weight=1.0,
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client

    set_storage(None)
    await engine.dispose()


@pytest.fixture
def future_exam_date() -> str:
    return (datetime.now(UTC) + timedelta(days=60)).isoformat()
