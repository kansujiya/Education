"""Export agent: turn a topic's lesson + mind map + cards into a
downloadable bundle and persist an Artefact row.

Pipeline:

  1. Read lesson (from ``lessons``), cards (from ``cards``), and the
     latest mind-map artefacts handed in by the caller.
  2. Call ``mcp-pdf.bundle_markdown_zip`` to build the ZIP.
  3. Write bytes through the configured Storage abstraction.
  4. Insert an ``Artefact`` row pointing at the storage key.

The mind-map SVG is read off disk for the M-2 demo (`out/<topic>/`); a
later milestone can move it to Storage too.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import models as orm
from api.db.repositories import CardRepo
from api.mcp import MCPClient, MCPServerSpec
from api.storage import Storage, get_storage


def default_pdf_spec() -> MCPServerSpec:
    return MCPServerSpec(command="python", args=["-m", "mcp_pdf.server"], env=os.environ.copy())


@dataclass(slots=True)
class ExportResult:
    artefact_id: str
    object_key: str
    url: str
    size_bytes: int


class ExportAgent:
    def __init__(
        self,
        client: MCPClient | None = None,
        storage: Storage | None = None,
    ) -> None:
        self._client = client or MCPClient(default_pdf_spec())
        self._storage = storage  # None → resolved per call from get_storage()

    async def export(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        topic_id: str,
        topic_title: str,
        lesson_md: str,
        mindmap_svg: str,
        mindmap_mermaid: str,
    ) -> ExportResult:
        cards_rows = await CardRepo(db, user_id).list_for_topic(topic_id)
        cards_payload = [
            {
                "type": c.type,
                "prompt": c.prompt,
                "answer": c.answer,
                "key_points": list(c.key_points or []),
                "source_pyq_id": c.source_pyq_id,
            }
            for c in cards_rows
        ]

        result = await self._client.call(
            "bundle_markdown_zip",
            {
                "topic_id": topic_id,
                "topic_title": topic_title,
                "lesson_md": lesson_md,
                "mindmap_svg": mindmap_svg,
                "mindmap_mermaid": mindmap_mermaid,
                "cards": cards_payload,
            },
        )
        if not isinstance(result, dict) or "base64" not in result:
            raise RuntimeError(f"mcp-pdf returned unexpected payload: {result!r}")

        raw = base64.b64decode(result["base64"])
        storage = self._storage or get_storage()
        key = f"users/{user_id}/topics/{topic_id}/bundle.zip"
        obj = await storage.put(key, raw, content_type="application/zip")

        artefact = orm.Artefact(
            id=f"art_{user_id[:6]}_{topic_id[:24]}_{int(obj.size_bytes):x}",
            user_id=user_id,
            topic_id=topic_id,
            kind="markdown_zip",
            object_key=obj.key,
        )
        db.add(artefact)
        await db.flush()

        return ExportResult(
            artefact_id=artefact.id,
            object_key=obj.key,
            url=obj.url,
            size_bytes=obj.size_bytes,
        )

    @staticmethod
    def cards_payload_from_rows(rows: list[orm.Card]) -> list[dict[str, object]]:
        """Helper exposed so callers can preview what'll be written."""
        return [
            {
                "type": c.type,
                "prompt": c.prompt,
                "answer": c.answer,
                "key_points": list(c.key_points or []),
                "source_pyq_id": c.source_pyq_id,
            }
            for c in rows
        ]
