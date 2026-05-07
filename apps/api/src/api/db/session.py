"""Async SQLAlchemy session factory + context-manager helper.

Driver is selected from the URL: ``postgresql+asyncpg://...`` for prod /
docker-compose, ``sqlite+aiosqlite:///:memory:`` for tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.config import settings


def _async_url(url: str) -> str:
    """Translate the configured DATABASE_URL to an async driver URL."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(_async_url(settings.database_url), echo=False, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


def reset_engine_cache() -> None:
    """Drop cached engine/factory; tests use this between fixtures."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
