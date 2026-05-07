"""Repositories — the only path between business code and the DB.

Two rules:
- User-owned tables (sessions, lessons, cards, progress, artefacts,
  plans, profiles) are queried via ``UserScopedRepo`` which always
  applies ``WHERE user_id = :user_id`` at the SQL layer.
- Global tables (exams, syllabus_topics) are queried via plain repos.

This separation is what lets us prove, in tests, that user A can never
read user B's rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

from shared.models import SyllabusTopic as SyllabusTopicModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import models as orm

# ---- Global (un-scoped) repos ----------------------------------------


class ExamRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert(self, exam_id: str, name: str, slug: str) -> orm.Exam:
        existing = await self.s.get(orm.Exam, exam_id)
        if existing is None:
            existing = orm.Exam(id=exam_id, name=name, slug=slug)
            self.s.add(existing)
        else:
            existing.name = name
            existing.slug = slug
        await self.s.flush()
        return existing


class SyllabusRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def replace_for_exam(self, exam_id: str, topics: list[SyllabusTopicModel]) -> int:
        """Replace the topic tree for an exam in one transaction.

        Returns the number of topics written.
        """
        # Wipe existing topics for this exam first.
        existing = await self.s.execute(
            select(orm.SyllabusTopic).where(orm.SyllabusTopic.exam_id == exam_id)
        )
        for row in existing.scalars().all():
            await self.s.delete(row)
        await self.s.flush()

        flat: list[SyllabusTopicModel] = []
        _flatten_inplace(topics, flat)
        # Parents must exist before children.
        flat.sort(key=lambda t: (t.parent_id is not None, t.id))
        for t in flat:
            self.s.add(
                orm.SyllabusTopic(
                    id=t.id,
                    exam_id=exam_id,
                    parent_id=t.parent_id,
                    title=t.title,
                    weight=t.weight,
                )
            )
        await self.s.flush()
        return len(flat)

    async def fetch_tree(self, exam_id: str) -> list[SyllabusTopicModel]:
        rows = (
            (
                await self.s.execute(
                    select(orm.SyllabusTopic).where(orm.SyllabusTopic.exam_id == exam_id)
                )
            )
            .scalars()
            .all()
        )
        nodes = {
            r.id: SyllabusTopicModel(
                id=r.id,
                exam_id=r.exam_id,
                parent_id=r.parent_id,
                title=r.title,
                weight=r.weight,
            )
            for r in rows
        }
        roots: list[SyllabusTopicModel] = []
        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots


def _flatten_inplace(topics: list[SyllabusTopicModel], out: list[SyllabusTopicModel]) -> None:
    for t in topics:
        out.append(t)
        if t.children:
            _flatten_inplace(t.children, out)


# ---- User-scoped repos ----------------------------------------------

T = TypeVar("T")


class UserScopedRepo:
    """Base class enforcing user_id on every query.

    Every method takes ``user_id`` and applies it as a WHERE clause.
    Subclasses must NOT add un-scoped queries.
    """

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        if not user_id:
            raise ValueError("UserScopedRepo requires a non-empty user_id")
        self.s = session
        self.user_id = user_id


class SessionRepo(UserScopedRepo):
    async def upsert(self, agent: str, state: dict[str, object]) -> orm.Session:
        existing = (
            await self.s.execute(
                select(orm.Session).where(
                    orm.Session.user_id == self.user_id,
                    orm.Session.agent == agent,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = orm.Session(
                id=f"sess_{self.user_id}_{agent}",
                user_id=self.user_id,
                agent=agent,
                state=state,
            )
            self.s.add(existing)
        else:
            existing.state = state
        await self.s.flush()
        return existing

    async def get(self, agent: str) -> orm.Session | None:
        return (
            await self.s.execute(
                select(orm.Session).where(
                    orm.Session.user_id == self.user_id,
                    orm.Session.agent == agent,
                )
            )
        ).scalar_one_or_none()


class CardRepo(UserScopedRepo):
    """Cards (flashcards / MCQ / short-answer) issued by the Assessor.

    All queries scoped by ``user_id``. ``topic_id`` is a global FK; the
    same topic id is shared across users but each user has their own
    cards (different prompts/answers per user level / progress).
    """

    async def add_many(self, cards: list[dict[str, object]]) -> list[orm.Card]:
        rows: list[orm.Card] = []
        for c in cards:
            kp_raw = c.get("key_points") or []
            row = orm.Card(
                id=str(c.get("id") or f"card_{uuid4().hex[:12]}"),
                user_id=self.user_id,
                topic_id=str(c["topic_id"]),
                type=str(c["type"]),
                prompt=str(c["prompt"]),
                answer=str(c["answer"]),
                key_points=list(kp_raw) if isinstance(kp_raw, list) else [],
                source_pyq_id=str(c["source_pyq_id"]) if c.get("source_pyq_id") else None,
            )
            self.s.add(row)
            rows.append(row)
        await self.s.flush()
        return rows

    async def list_for_topic(self, topic_id: str) -> list[orm.Card]:
        return list(
            (
                await self.s.execute(
                    select(orm.Card).where(
                        orm.Card.user_id == self.user_id,
                        orm.Card.topic_id == topic_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    async def get(self, card_id: str) -> orm.Card | None:
        row = await self.s.get(orm.Card, card_id)
        if row is None or row.user_id != self.user_id:
            return None
        return row


class CardAttemptRepo(UserScopedRepo):
    async def add(
        self,
        card_id: str,
        score: float,
        *,
        due_at: datetime | None = None,
        attempt_at: datetime | None = None,
    ) -> orm.CardAttempt:
        row = orm.CardAttempt(
            id=f"att_{uuid4().hex[:12]}",
            card_id=card_id,
            user_id=self.user_id,
            attempt_at=attempt_at or datetime.now(UTC),
            score=score,
            due_at=due_at,
        )
        self.s.add(row)
        await self.s.flush()
        return row

    async def list_for_card(self, card_id: str) -> list[orm.CardAttempt]:
        return list(
            (
                await self.s.execute(
                    select(orm.CardAttempt)
                    .where(
                        orm.CardAttempt.user_id == self.user_id,
                        orm.CardAttempt.card_id == card_id,
                    )
                    .order_by(orm.CardAttempt.attempt_at.asc())
                )
            )
            .scalars()
            .all()
        )

    async def list_for_topic(self, topic_id: str) -> list[orm.CardAttempt]:
        """Return attempts for any card on this topic (joined via cards.topic_id)."""
        cards_q = select(orm.Card.id).where(
            orm.Card.user_id == self.user_id, orm.Card.topic_id == topic_id
        )
        return list(
            (
                await self.s.execute(
                    select(orm.CardAttempt)
                    .where(
                        orm.CardAttempt.user_id == self.user_id,
                        orm.CardAttempt.card_id.in_(cards_q),
                    )
                    .order_by(orm.CardAttempt.attempt_at.asc())
                )
            )
            .scalars()
            .all()
        )


class ProgressRepo(UserScopedRepo):
    async def upsert(
        self,
        topic_id: str,
        *,
        mastery: float,
        predicted_readiness: float | None = None,
    ) -> orm.Progress:
        existing = await self.s.get(orm.Progress, (self.user_id, topic_id))
        if existing is None:
            existing = orm.Progress(
                user_id=self.user_id,
                topic_id=topic_id,
                mastery=mastery,
                predicted_readiness=predicted_readiness or 0.0,
                last_touched=datetime.now(UTC),
            )
            self.s.add(existing)
        else:
            existing.mastery = mastery
            if predicted_readiness is not None:
                existing.predicted_readiness = predicted_readiness
            existing.last_touched = datetime.now(UTC)
        await self.s.flush()
        return existing

    async def get(self, topic_id: str) -> orm.Progress | None:
        return await self.s.get(orm.Progress, (self.user_id, topic_id))

    async def list_all(self) -> list[orm.Progress]:
        return list(
            (await self.s.execute(select(orm.Progress).where(orm.Progress.user_id == self.user_id)))
            .scalars()
            .all()
        )


class ProfileRepo(UserScopedRepo):
    """One row per user (the active study profile)."""

    async def upsert(
        self,
        *,
        exam_id: str,
        exam_date: datetime,
        daily_minutes: int,
        level: str = "novice",
    ) -> orm.Profile:
        existing = await self.s.get(orm.Profile, self.user_id)
        if existing is None:
            existing = orm.Profile(
                user_id=self.user_id,
                exam_id=exam_id,
                exam_date=exam_date,
                daily_minutes=daily_minutes,
                level=level,
            )
            self.s.add(existing)
        else:
            existing.exam_id = exam_id
            existing.exam_date = exam_date
            existing.daily_minutes = daily_minutes
            existing.level = level
        await self.s.flush()
        return existing

    async def get(self) -> orm.Profile | None:
        return await self.s.get(orm.Profile, self.user_id)


class PlanRepo(UserScopedRepo):
    async def save(self, schedule: dict[str, object]) -> orm.Plan:
        row = orm.Plan(
            id=f"plan_{uuid4().hex[:12]}",
            user_id=self.user_id,
            generated_at=datetime.now(UTC),
            schedule=schedule,
        )
        self.s.add(row)
        await self.s.flush()
        return row

    async def latest(self) -> orm.Plan | None:
        return (
            await self.s.execute(
                select(orm.Plan)
                .where(orm.Plan.user_id == self.user_id)
                .order_by(orm.Plan.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()


class UserRepo:
    """Manages user rows; intentionally not user-scoped (admin-ish)."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert(
        self,
        user_id: str,
        email: str,
        name: str | None = None,
        *,
        language: str | None = None,
    ) -> orm.User:
        """Insert or update a user. ``language`` is preserved if not given."""
        existing = await self.s.get(orm.User, user_id)
        if existing is None:
            existing = orm.User(
                id=user_id,
                email=email,
                name=name,
                language=language or "en",
            )
            self.s.add(existing)
        else:
            existing.email = email
            existing.name = name
            if language is not None:
                existing.language = language
        await self.s.flush()
        return existing

    async def set_language(self, user_id: str, language: str) -> orm.User:
        user = await self.s.get(orm.User, user_id)
        if user is None:
            raise LookupError(f"unknown user_id={user_id!r}")
        user.language = language
        await self.s.flush()
        return user

    async def get(self, user_id: str) -> orm.User | None:
        return await self.s.get(orm.User, user_id)
