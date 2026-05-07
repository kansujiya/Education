"""Coach agent — orchestrator-workers + autonomous-replan pattern.

For v0.1 the planning core is deterministic (``api.planning.compute_plan``);
the Coach orchestrates: pull the user's profile, syllabus, PYQ frequencies,
and current progress; compose a plan; persist it; emit no event of its own
(callers that want to react do so on ``plan.replan`` / ``user.onboarded``).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories import (
    PlanRepo,
    ProfileRepo,
    ProgressRepo,
    SyllabusRepo,
)
from api.planning import StudyPlan, compute_plan


@dataclass(slots=True)
class PlanResult:
    plan: StudyPlan
    plan_id: str


class CoachAgent:
    """Composes a study plan from current state.

    ``pyq_frequency`` is injected — the caller (CLI / listener) is in
    charge of fetching it via ``mcp-pyq``. This keeps the Coach pure +
    testable without spawning subprocesses.
    """

    async def plan(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        pyq_frequency: dict[str, int],
        days_window: int = 7,
    ) -> PlanResult:
        profile = await ProfileRepo(db, user_id).get()
        if profile is None:
            raise LookupError(f"no profile for user_id={user_id!r}; onboard first")

        topics = await SyllabusRepo(db).fetch_tree(profile.exam_id)
        progress_rows = await ProgressRepo(db, user_id).list_all()
        progress = {p.topic_id: p.mastery for p in progress_rows}

        plan = compute_plan(
            user_id=user_id,
            exam_id=profile.exam_id,
            exam_date=profile.exam_date,
            daily_minutes=profile.daily_minutes,
            topics=topics,
            pyq_frequency=pyq_frequency,
            progress=progress,
            days_window=days_window,
        )
        row = await PlanRepo(db, user_id).save(plan.to_dict())
        return PlanResult(plan=plan, plan_id=row.id)
