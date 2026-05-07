"""SQLAlchemy ORM models.

These mirror the data model in ``tech-plan.md`` §10. Vector columns for
RAG are added in a later migration (M-2) and live on a separate model
file so SQLite-based tests don't need pgvector.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base for all ORM models."""


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    exam_id: Mapped[str] = mapped_column(String(64), ForeignKey("exams.id"), nullable=False)
    exam_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60)
    level: Mapped[str] = mapped_column(String(16), default="novice")


class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    exam_id: Mapped[str] = mapped_column(String(64), ForeignKey("exams.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("syllabus_topics.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    children: Mapped[list[SyllabusTopic]] = relationship(
        "SyllabusTopic",
        backref="parent",
        remote_side="SyllabusTopic.id",
        viewonly=True,
    )


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (UniqueConstraint("user_id", "agent", name="uq_sessions_user_agent"),)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("syllabus_topics.id"), nullable=False
    )
    content_md: Mapped[str] = mapped_column(Text, default="")
    mindmap_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("syllabus_topics.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # recall|mcq|short
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source_pyq_id: Mapped[str | None] = mapped_column(String(64))


class CardAttempt(Base):
    __tablename__ = "card_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(String(36), ForeignKey("cards.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Progress(Base):
    __tablename__ = "progress"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("syllabus_topics.id"), primary_key=True
    )
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    last_touched: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    predicted_readiness: Mapped[float] = mapped_column(Float, default=0.0)


class Artefact(Base):
    __tablename__ = "artefacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("syllabus_topics.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf|markdown_zip
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EventRow(Base):
    """Append-only audit log of every event emitted on the bus."""

    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
