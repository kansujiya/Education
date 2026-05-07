"""language preference on users

Revision ID: 0002_user_language
Revises: 0001_initial
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_language"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "language",
            sa.String(2),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("language")
