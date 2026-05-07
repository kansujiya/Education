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

from typing import TypeVar

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
