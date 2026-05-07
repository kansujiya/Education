"""Domain Pydantic models shared across services.

Database rows have their own SQLAlchemy ORM models; these are the
public-facing Pydantic types used at every API boundary, in tool I/O,
and in event payloads. Keeping them here means the shape is the same
whether a value comes from the DB, an MCP server, or a JSON event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TopicStatus = Literal["not_started", "in_progress", "mastered"]


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str | None = None
    created_at: datetime


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    exam_id: str
    exam_date: datetime
    daily_minutes: int = 60
    level: Literal["novice", "intermediate", "advanced"] = "novice"


class Exam(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str


class SyllabusTopic(BaseModel):
    """One node in the syllabus tree.

    `parent_id` makes the tree explicit; the in-memory `children` list is
    populated by the repository when the whole tree is requested.
    """

    model_config = ConfigDict(from_attributes=True)
    id: str
    exam_id: str
    parent_id: str | None = None
    title: str
    weight: float = Field(default=1.0, ge=0.0, description="Relative importance / PYQ frequency.")
    children: list[SyllabusTopic] = Field(default_factory=list)


class Session(BaseModel):
    """A per-user, per-agent slice of working memory."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    agent: str
    state: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime
