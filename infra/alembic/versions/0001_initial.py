"""initial schema (no pgvector; that lands in M-2)

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "exams",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "syllabus_topics",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("exam_id", sa.String(64), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("parent_id", sa.String(128), sa.ForeignKey("syllabus_topics.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_syllabus_topics_exam", "syllabus_topics", ["exam_id"])

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("exam_id", sa.String(64), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("exam_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("daily_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("level", sa.String(16), nullable=False, server_default="novice"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "agent", name="uq_sessions_user_agent"),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])

    op.create_table(
        "plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schedule", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_plans_user", "plans", ["user_id"])

    op.create_table(
        "lessons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(128), sa.ForeignKey("syllabus_topics.id"), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("mindmap_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lessons_user_topic", "lessons", ["user_id", "topic_id"])

    op.create_table(
        "cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(128), sa.ForeignKey("syllabus_topics.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source_pyq_id", sa.String(64)),
    )
    op.create_index("ix_cards_user_topic", "cards", ["user_id", "topic_id"])

    op.create_table(
        "card_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_card_attempts_user", "card_attempts", ["user_id"])

    op.create_table(
        "progress",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "topic_id", sa.String(128), sa.ForeignKey("syllabus_topics.id"), primary_key=True
        ),
        sa.Column("mastery", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_touched", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_readiness", sa.Float(), nullable=False, server_default="0.0"),
    )

    op.create_table(
        "artefacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(128), sa.ForeignKey("syllabus_topics.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artefacts_user", "artefacts", ["user_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(36)),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_events_name", "events", ["name"])
    op.create_index("ix_events_user", "events", ["user_id"])


def downgrade() -> None:
    for tbl in [
        "events",
        "artefacts",
        "progress",
        "card_attempts",
        "cards",
        "lessons",
        "plans",
        "sessions",
        "profiles",
        "syllabus_topics",
        "exams",
        "users",
    ]:
        op.drop_table(tbl)
