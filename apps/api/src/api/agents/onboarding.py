"""Onboarding agent — collects exam, date, daily minutes, level.

Pattern: **prompt chaining** (collect-fields → score-diagnostic → write-profile).

For v0.1 the LLM-driven diagnostic is a follow-up; the agent is a thin
wrapper that validates + persists the profile and emits ``user.onboarded``
so listeners (Coach, Insight cache) know to take action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from redis.asyncio import Redis
from shared.events import UserOnboarded
from shared.models import Language
from sqlalchemy.ext.asyncio import AsyncSession

from api.bus.events import emit_event
from api.db import models as orm
from api.db.repositories import ProfileRepo, UserRepo

Level = Literal["novice", "intermediate", "advanced"]


@dataclass(slots=True)
class OnboardingResult:
    user: orm.User
    profile: orm.Profile


class OnboardingAgent:
    """Persist a profile and emit ``user.onboarded``.

    Real LLM-side reasoning (level estimation from a quick diagnostic)
    will be layered on top later; the persistence + event contract this
    agent owns is what downstream listeners depend on.
    """

    async def run(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        email: str,
        exam_id: str,
        exam_date: datetime,
        daily_minutes: int = 60,
        level: Level = "novice",
        language: Language = "en",
        redis: Redis | None = None,
    ) -> OnboardingResult:
        if daily_minutes <= 0:
            raise ValueError("daily_minutes must be > 0")
        if exam_date <= datetime.now(exam_date.tzinfo):
            raise ValueError("exam_date must be in the future")

        users = UserRepo(db)
        profiles = ProfileRepo(db, user_id)

        user = await users.upsert(user_id, email=email, language=language)
        profile = await profiles.upsert(
            exam_id=exam_id,
            exam_date=exam_date,
            daily_minutes=daily_minutes,
            level=level,
        )
        await db.flush()

        if redis is not None:
            await emit_event(
                UserOnboarded(user_id=user_id, exam_id=exam_id, daily_minutes=daily_minutes),
                redis=redis,
                db=db,
            )
        await db.commit()
        return OnboardingResult(user=user, profile=profile)
