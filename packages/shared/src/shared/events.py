"""Event payload models for the Redis Streams bus.

Every event has a versioned name and a typed payload. Producers emit a
specific subclass; consumers parse via ``Event.from_envelope``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

EventName = Literal[
    "user.onboarded",
    "topic.taught",
    "topic.understood",
    "topic.misunderstood",
    "card.attempted",
    "topic.mastered",
    "plan.replan",
    "user.idle_3d",
    "exam.t-14d",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _BaseEvent(BaseModel):
    """Common envelope: every event carries name, version, ids, time."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex)
    version: int = 1
    emitted_at: datetime = Field(default_factory=_utcnow)
    correlation_id: str | None = None
    user_id: str | None = None


class UserOnboarded(_BaseEvent):
    name: Literal["user.onboarded"] = "user.onboarded"
    exam_id: str
    daily_minutes: int


class TopicTaught(_BaseEvent):
    name: Literal["topic.taught"] = "topic.taught"
    topic_id: str


class TopicUnderstood(_BaseEvent):
    name: Literal["topic.understood"] = "topic.understood"
    topic_id: str
    score: float


class TopicMisunderstood(_BaseEvent):
    name: Literal["topic.misunderstood"] = "topic.misunderstood"
    topic_id: str
    gap: str


class CardAttempted(_BaseEvent):
    name: Literal["card.attempted"] = "card.attempted"
    card_id: str
    topic_id: str
    score: float
    correct: bool


class TopicMastered(_BaseEvent):
    name: Literal["topic.mastered"] = "topic.mastered"
    topic_id: str
    mastery: float


class PlanReplan(_BaseEvent):
    name: Literal["plan.replan"] = "plan.replan"
    reason: str


class UserIdle3d(_BaseEvent):
    name: Literal["user.idle_3d"] = "user.idle_3d"


class ExamT14d(_BaseEvent):
    name: Literal["exam.t-14d"] = "exam.t-14d"
    exam_id: str


Event = Annotated[
    UserOnboarded
    | TopicTaught
    | TopicUnderstood
    | TopicMisunderstood
    | CardAttempted
    | TopicMastered
    | PlanReplan
    | UserIdle3d
    | ExamT14d,
    Field(discriminator="name"),
]


_event_adapter: TypeAdapter[Event] = TypeAdapter(Event)


def parse_event(payload: dict[str, Any]) -> Event:
    """Parse an envelope dict into the right concrete event type."""
    return _event_adapter.validate_python(payload)
