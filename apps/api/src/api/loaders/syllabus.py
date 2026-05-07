"""Bring an exam syllabus into the DB by calling the syllabus MCP server.

Pipeline:
  1. Spawn ``mcp-syllabus`` (Python module) over stdio.
  2. Call ``fetch_syllabus(exam_id=...)``.
  3. Validate response into shared Pydantic models.
  4. Upsert exam + replace topic tree via repositories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from shared.tools import FetchSyllabusOutput
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories import ExamRepo, SyllabusRepo
from api.mcp import MCPClient, MCPServerSpec

DEFAULT_SYLLABUS_SPEC = MCPServerSpec(
    command="python",
    args=["-m", "mcp_syllabus.server"],
    env=os.environ.copy(),
)


@dataclass(slots=True)
class LoadResult:
    exam_id: str
    name: str
    topic_count: int


class SyllabusLoader:
    """Calls the MCP server and writes the result through the repos."""

    def __init__(self, mcp: MCPClient | None = None) -> None:
        self._mcp = mcp or MCPClient(DEFAULT_SYLLABUS_SPEC)

    async def load(self, db: AsyncSession, exam_id: str) -> LoadResult:
        raw = await self._mcp.call("fetch_syllabus", {"exam_id": exam_id})
        if raw is None:
            raise RuntimeError(f"mcp-syllabus returned nothing for exam_id={exam_id!r}")
        parsed = FetchSyllabusOutput.model_validate(raw)
        await ExamRepo(db).upsert(parsed.exam_id, parsed.name, parsed.exam_id)
        count = await SyllabusRepo(db).replace_for_exam(parsed.exam_id, parsed.topics)
        return LoadResult(exam_id=parsed.exam_id, name=parsed.name, topic_count=count)


async def load_exam_via_mcp(db: AsyncSession, exam_id: str) -> LoadResult:
    return await SyllabusLoader().load(db, exam_id)
