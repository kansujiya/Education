"""``/v1/me/*`` — per-user endpoints. All scoped via JWT ``sub``.

Tutor / Examiner / Assessor agents need an Anthropic-like client. The
production app builds a real ``anthropic.Anthropic`` once at startup
and injects it via the ``get_llm_client`` dependency. Tests override
the dependency with a deterministic fake (the eval fake from
``apps/api/tests/conftest.py``).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from shared.events import CardAttempted
from sqlalchemy.ext.asyncio import AsyncSession

from api.agents import (
    AssessorAgent,
    CardSpec,
    CoachAgent,
    ExportAgent,
    OnboardingAgent,
    TutorAgent,
)
from api.bus.events import emit_event
from api.db import models as orm
from api.db.repositories import (
    CardAttemptRepo,
    CardRepo,
    PlanRepo,
    ProfileRepo,
    ProgressRepo,
    UserRepo,
)
from api.listeners import dispatch_event
from api.rag import NotesIndex
from api.web.deps import CurrentUser, get_bus, get_db

router = APIRouter(prefix="/v1/me", tags=["me"])


# ---- LLM client dependency ------------------------------------------


def get_llm_client() -> Any:  # pragma: no cover — production path
    from anthropic import Anthropic

    from api.config import settings

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY not configured on the server"
        )
    return Anthropic(api_key=settings.anthropic_api_key)


REPO_ROOT = Path(__file__).resolve().parents[6]
_NOTES_PATH = REPO_ROOT / "seeds" / "notes_aws_ccp.jsonl"


def get_notes_index() -> NotesIndex:
    """Process-level singleton; cheap to keep loaded."""
    return NotesIndex.from_jsonl(_NOTES_PATH)


# ---- Request / response shapes --------------------------------------


class ProfileRequest(BaseModel):
    exam_id: str
    exam_date: datetime
    daily_minutes: int = Field(60, gt=0, le=24 * 60)
    level: str = "novice"
    language: str = "en"


class AttemptRequest(BaseModel):
    answer: str = Field(min_length=1)


# ---- Profile / plan -------------------------------------------------


@router.post("/profile")
async def set_profile(
    req: ProfileRequest,
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
    bus: Redis = Depends(get_bus),
) -> dict[str, Any]:
    user = await UserRepo(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    agent = OnboardingAgent()
    result = await agent.run(
        db,
        user_id=user_id,
        email=user.email,
        exam_id=req.exam_id,
        exam_date=req.exam_date,
        daily_minutes=req.daily_minutes,
        level=req.level,  # type: ignore[arg-type]
        language=req.language if req.language in ("en", "hi") else "en",  # type: ignore[arg-type]
        redis=bus,
    )
    return {
        "user_id": result.user.id,
        "exam_id": result.profile.exam_id,
        "exam_date": result.profile.exam_date.isoformat(),
        "daily_minutes": result.profile.daily_minutes,
        "level": result.profile.level,
        "language": result.user.language,
    }


@router.get("/plan")
async def get_plan(
    user_id: Annotated[str, CurrentUser],
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    bus: Redis = Depends(get_bus),
) -> dict[str, Any]:
    profile = await ProfileRepo(db, user_id).get()
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile; POST /v1/me/profile first")
    # For HTTP we use an empty PYQ frequency map; the CLI/MCP path lives in CLI.
    coach = CoachAgent()
    result = await coach.plan(db, user_id=user_id, pyq_frequency={}, days_window=days)
    await db.commit()
    return result.plan.to_dict()


# ---- Cards / attempts / progress ------------------------------------


@router.post("/topics/{topic_id}/cards")
async def issue_cards(
    topic_id: str,
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
    client: Any = Depends(get_llm_client),
    notes: NotesIndex = Depends(get_notes_index),
) -> dict[str, Any]:
    """Generate cards via the Assessor and persist them.

    The Tutor lesson is regenerated from notes for grounding context;
    real prod will reuse the cached ``lessons`` row.
    """
    tutor = TutorAgent(client=client, notes=notes)
    chunks_iter, _ = tutor.stream_lesson(topic_id, topic_id, language="en")
    lesson_md = "".join(chunks_iter)

    assessor = AssessorAgent(client=client)
    specs = assessor.issue_cards(topic_id, lesson_md, pyqs=[], n=6)
    persisted = await CardRepo(db, user_id).add_many(
        [
            {
                "topic_id": topic_id,
                "type": s.type,
                "prompt": s.prompt,
                "answer": s.answer,
                "key_points": list(s.key_points),
                "source_pyq_id": s.source_pyq_id,
            }
            for s in specs
        ]
    )
    await db.commit()
    return {
        "cards": [
            {
                "id": row.id,
                "type": row.type,
                "prompt": row.prompt,
                "source_pyq_id": row.source_pyq_id,
            }
            for row in persisted
        ]
    }


@router.post("/cards/{card_id}/attempt")
async def attempt_card(
    card_id: str,
    body: Annotated[AttemptRequest, Body()],
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
    bus: Redis = Depends(get_bus),
    client: Any = Depends(get_llm_client),
) -> dict[str, Any]:
    card = await CardRepo(db, user_id).get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"no card {card_id!r}")
    spec = CardSpec.model_validate(
        {
            "type": card.type,
            "prompt": card.prompt,
            "answer": card.answer,
            "key_points": list(card.key_points or []),
            "source_pyq_id": card.source_pyq_id,
        }
    )
    judgement = AssessorAgent(client=client).grade_attempt(spec, body.answer)
    attempt_row = await CardAttemptRepo(db, user_id).add(card_id=card_id, score=judgement.score)
    await db.commit()

    event = CardAttempted(
        user_id=user_id,
        card_id=card_id,
        topic_id=card.topic_id,
        score=judgement.score,
        correct=judgement.correct,
    )
    await emit_event(event, redis=bus, db=db)
    await db.commit()
    await dispatch_event(event, db=db, redis=bus)
    await db.commit()

    return {
        "score": judgement.score,
        "correct": judgement.correct,
        "gap": judgement.gap,
        "due_at": attempt_row.due_at.isoformat() if attempt_row.due_at else None,
    }


@router.get("/progress")
async def get_progress(
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await ProgressRepo(db, user_id).list_all()
    rows.sort(key=lambda r: r.mastery, reverse=True)
    return {
        "topics": [
            {
                "topic_id": r.topic_id,
                "mastery": r.mastery,
                "last_touched": r.last_touched.isoformat(),
            }
            for r in rows
        ]
    }


# ---- Export ----------------------------------------------------------


class ExportRequest(BaseModel):
    topic_title: str = ""
    lesson_md: str = ""
    mindmap_svg: str = ""
    mindmap_mermaid: str = ""


@router.post("/topics/{topic_id}/export")
async def export_topic(
    topic_id: str,
    body: Annotated[ExportRequest, Body()],
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
    export_agent: ExportAgent = Depends(lambda: ExportAgent()),
) -> dict[str, Any]:
    result = await export_agent.export(
        db,
        user_id=user_id,
        topic_id=topic_id,
        topic_title=body.topic_title or topic_id,
        lesson_md=body.lesson_md,
        mindmap_svg=body.mindmap_svg or "<svg/>",
        mindmap_mermaid=body.mindmap_mermaid,
    )
    await db.commit()
    return {
        "artefact_id": result.artefact_id,
        "url": result.url,
        "size_bytes": result.size_bytes,
    }


# ---- Latest plan handle (auxiliary) ---------------------------------


@router.get("/plan/latest")
async def latest_plan(
    user_id: Annotated[str, CurrentUser],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await PlanRepo(db, user_id).latest()
    if row is None:
        return {"plan": None}
    return {"plan_id": row.id, "schedule": dict(row.schedule)}


# Keep ORM imported (silences mypy --strict otherwise).
_KEEP: type[orm.User] = orm.User
