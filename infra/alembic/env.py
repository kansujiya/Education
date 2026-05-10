"""Alembic environment configured for Education AI.

Reads ``DATABASE_URL`` from the project-root ``.env`` (or the OS env)
and points autogenerate at the ORM metadata defined in ``api.db.models``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

# Project root contains ``.env``. We're at infra/alembic/env.py, so ../..
ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Load ``.env`` from the project root if present.

    The Makefile invokes alembic with ``cd infra/alembic`` so the project-
    root ``.env`` would otherwise be invisible. We parse the file by hand
    (no python-dotenv dependency) so DATABASE_URL is honoured regardless
    of CWD. Keys already set in the environment win — env > file.
    """
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Make src layouts importable when alembic is invoked from any cwd.
for path in [
    ROOT / "apps" / "api" / "src",
    ROOT / "packages" / "shared" / "src",
]:
    sys.path.insert(0, str(path))

from api.db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Resolve URL with this priority:
# 1) An explicit sqlalchemy.url set on the Config (e.g. by tests via Config.set_main_option).
# 2) DATABASE_URL env var (production / docker-compose / loaded from .env above).
# 3) A SQLite fallback for ad-hoc local invocation.
def _resolve_url() -> str:
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    return "sqlite:///./dev.db"


config.set_main_option("sqlalchemy.url", _resolve_url())

target_metadata = Base.metadata


def _is_async(url: str) -> bool:
    return "+asyncpg" in url or "+aiosqlite" in url


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_async() -> None:
    cfg_section = config.get_section(config.config_ini_section, {})
    engine = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    if isinstance(engine, AsyncEngine):
        async with engine.connect() as connection:
            await connection.run_sync(_do_run_migrations)
        await engine.dispose()
        return
    with engine.connect() as connection:  # type: ignore[union-attr]
        _do_run_migrations(connection)


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or ""
    if _is_async(url):
        asyncio.run(_run_migrations_async())
        return
    cfg_section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        _do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
