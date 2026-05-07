"""M-6 demo lock-in: ExportAgent + Storage + Artefact persistence.

Stubs ``MCPClient`` so we don't spawn ``mcp-pdf`` here (its bundle assembly
is covered by ``mcp/pdf/tests``). The agent-level invariants:

  - bundle bytes round-trip through the configured Storage,
  - the resulting URL is downloadable and the ZIP contains the expected
    files, and
  - an Artefact row is written under the correct user.
"""

from __future__ import annotations

import base64
import io
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import pytest
from api.agents.export import ExportAgent
from api.db import models as orm
from api.db.repositories import CardRepo, UserRepo
from api.storage import LocalStorage


class _BundleStubClient:
    """Returns a real ZIP, base64-encoded, mimicking ``mcp-pdf``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        from mcp_pdf.bundle import build_zip

        self.calls.append((tool, args))
        raw = build_zip(
            topic_id=str(args["topic_id"]),
            topic_title=str(args["topic_title"]),
            lesson_md=str(args["lesson_md"]),
            mindmap_svg=str(args["mindmap_svg"]),
            mindmap_mermaid=str(args["mindmap_mermaid"]),
            cards=list(args["cards"]),
        )
        return {
            "format": "zip",
            "size_bytes": len(raw),
            "base64": base64.b64encode(raw).decode("ascii"),
        }


async def _seed(db, user_id: str = "u_a", topic_id: str = "cloud-concepts.benefits"):
    db.add(orm.Exam(id="aws-ccp", name="AWS CCP", slug="aws-ccp"))
    db.add(orm.SyllabusTopic(id=topic_id, exam_id="aws-ccp", title="Benefits", weight=1.0))
    await UserRepo(db).upsert(user_id, email=f"{user_id}@x.com")
    await db.flush()
    cards = CardRepo(db, user_id)
    await cards.add_many(
        [
            {
                "id": "c1",
                "topic_id": topic_id,
                "type": "recall",
                "prompt": "What is pay-as-you-go?",
                "answer": "Pay only for what you use.",
                "key_points": ["pay-as-you-go"],
                "source_pyq_id": "pyq_001",
            }
        ]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_bundle_contains_lesson_mindmap_cards(db, tmp_path: Path) -> None:
    await _seed(db)
    storage = LocalStorage(tmp_path)
    agent = ExportAgent(client=_BundleStubClient(), storage=storage)  # type: ignore[arg-type]

    result = await agent.export(
        db,
        user_id="u_a",
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits of the Cloud",
        lesson_md="# Lesson\nThe cloud rents capacity.\n",
        mindmap_svg='<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>',
        mindmap_mermaid="mindmap\n  root((Benefits))\n",
    )

    raw = await storage.get(result.object_key)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert {"README.md", "lesson.md", "mindmap.svg", "cards.md", "cards.json"}.issubset(names)
        assert "rents capacity" in zf.read("lesson.md").decode()
        assert "<svg" in zf.read("mindmap.svg").decode()
        assert "pay-as-you-go" in zf.read("cards.md").decode()


@pytest.mark.asyncio
async def test_presigned_url_is_downloadable(db, tmp_path: Path) -> None:
    await _seed(db)
    storage = LocalStorage(tmp_path)
    agent = ExportAgent(client=_BundleStubClient(), storage=storage)  # type: ignore[arg-type]

    result = await agent.export(
        db,
        user_id="u_a",
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits of the Cloud",
        lesson_md="hi",
        mindmap_svg="<svg/>",
        mindmap_mermaid="mindmap",
    )

    # ``url`` is a file:// URL we can fetch as bytes.
    parsed = urllib.parse.urlparse(result.url)
    assert parsed.scheme == "file"
    fetched = urllib.request.urlopen(result.url).read()
    assert len(fetched) == result.size_bytes


@pytest.mark.asyncio
async def test_artefact_row_persisted_for_user(db, tmp_path: Path) -> None:
    await _seed(db)
    agent = ExportAgent(
        client=_BundleStubClient(),  # type: ignore[arg-type]
        storage=LocalStorage(tmp_path),
    )
    await agent.export(
        db,
        user_id="u_a",
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits",
        lesson_md="x",
        mindmap_svg="<svg/>",
        mindmap_mermaid="m",
    )
    rows = (
        await db.execute(orm.Artefact.__table__.select().where(orm.Artefact.user_id == "u_a"))
    ).all()
    assert len(rows) == 1
    assert rows[0].kind == "markdown_zip"
    assert rows[0].topic_id == "cloud-concepts.benefits"
