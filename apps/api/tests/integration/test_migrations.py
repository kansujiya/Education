"""M-1 migration check: 0001 applies and reverses cleanly on SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO = Path(__file__).resolve().parents[4]
ALEMBIC_DIR = REPO / "infra" / "alembic"


@pytest.fixture
def alembic_cfg(tmp_path):
    db_path = tmp_path / "test.sqlite"
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_initial_migration_up_then_down(alembic_cfg) -> None:
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    # If we got here, both directions worked.
