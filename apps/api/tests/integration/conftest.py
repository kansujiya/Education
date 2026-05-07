"""Integration-test fixtures: in-memory async SQLite DB + helper factories.

We don't need pgvector for M-1, so SQLite via aiosqlite is enough and
keeps CI hermetic (no Docker required).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from api.db import models as orm
from api.db.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory SQLite per test; schema created from ORM metadata."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
def now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def make_user(now):
    def _make(session: AsyncSession, user_id: str, email: str | None = None) -> orm.User:
        user = orm.User(id=user_id, email=email or f"{user_id}@example.com", created_at=now)
        session.add(user)
        return user

    return _make


@pytest.fixture
def make_exam():
    def _make(session: AsyncSession, exam_id: str = "aws-ccp") -> orm.Exam:
        exam = orm.Exam(id=exam_id, name=exam_id.upper(), slug=exam_id)
        session.add(exam)
        return exam

    return _make


@pytest.fixture
def make_topic():
    def _make(
        session: AsyncSession,
        topic_id: str,
        exam_id: str = "aws-ccp",
        parent_id: str | None = None,
        title: str | None = None,
        weight: float = 1.0,
    ) -> orm.SyllabusTopic:
        topic = orm.SyllabusTopic(
            id=topic_id,
            exam_id=exam_id,
            parent_id=parent_id,
            title=title or topic_id,
            weight=weight,
        )
        session.add(topic)
        return topic

    return _make
