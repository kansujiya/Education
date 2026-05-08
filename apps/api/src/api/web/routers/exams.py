"""``/v1/exams/*`` — global (un-scoped) exam metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.agents import InsightAgent
from api.db import models as orm
from api.db.repositories import SyllabusRepo
from api.web.deps import get_db

router = APIRouter(prefix="/v1/exams", tags=["exams"])


@router.get("")
async def list_exams(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    rows = (await db.execute(select(orm.Exam))).scalars().all()
    return {"exams": [{"id": r.id, "name": r.name, "slug": r.slug} for r in rows]}


@router.get("/{exam_id}/syllabus")
async def syllabus(exam_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tree = await SyllabusRepo(db).fetch_tree(exam_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown exam {exam_id!r}"
        )
    return {"exam_id": exam_id, "topics": [t.model_dump() for t in tree]}


@router.get("/{exam_id}/insights")
async def insights(exam_id: str, last_n_years: int = 5) -> dict[str, Any]:
    panel = await InsightAgent().panel(exam_id, last_n_years=last_n_years)
    return panel.to_dict()
