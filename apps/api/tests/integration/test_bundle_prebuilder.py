"""M-6: ``bundle_prebuilder`` listener fires on ``topic.mastered`` and
writes an Artefact row when a BundleSourceProvider is wired."""

from __future__ import annotations

from pathlib import Path

import pytest
from api.agents.export import ExportAgent
from api.db import models as orm
from api.db.repositories import UserRepo
from api.listeners import (
    BundleSource,
    dispatch_event,
    set_bundle_source_provider,
    set_export_agent,
)
from api.storage import LocalStorage
from fakeredis import aioredis as fake_aioredis
from shared.events import TopicMastered


class _BundleStubClient:
    """Same stub as in test_export_bundle — kept here so this test module
    has no cross-file dependency."""

    async def call(self, _tool: str, args: dict) -> dict:
        import base64

        from mcp_pdf.bundle import build_zip

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


@pytest.fixture
def fake_redis():
    return fake_aioredis.FakeRedis(decode_responses=True)


async def _seed(db, user_id: str, topic_id: str) -> None:
    db.add(orm.Exam(id="aws-ccp", name="AWS CCP", slug="aws-ccp"))
    db.add(orm.SyllabusTopic(id=topic_id, exam_id="aws-ccp", title="X", weight=1.0))
    await UserRepo(db).upsert(user_id, email=f"{user_id}@x.com")
    await db.commit()


@pytest.mark.asyncio
async def test_prebuilder_writes_artefact(db, fake_redis, tmp_path: Path) -> None:
    user_id = "u_a"
    topic_id = "cloud-concepts.benefits"
    await _seed(db, user_id, topic_id)

    async def provider(uid: str, tid: str) -> BundleSource:
        assert uid == user_id and tid == topic_id
        return BundleSource(
            topic_title="Benefits",
            lesson_md="cached lesson",
            mindmap_svg="<svg/>",
            mindmap_mermaid="mindmap",
        )

    set_bundle_source_provider(provider)
    set_export_agent(
        ExportAgent(client=_BundleStubClient(), storage=LocalStorage(tmp_path))  # type: ignore[arg-type]
    )
    try:
        event = TopicMastered(user_id=user_id, topic_id=topic_id, mastery=0.92)
        await dispatch_event(event, db=db, redis=fake_redis)
        await db.commit()
    finally:
        set_bundle_source_provider(None)
        set_export_agent(None)

    rows = (
        await db.execute(orm.Artefact.__table__.select().where(orm.Artefact.user_id == user_id))
    ).all()
    assert len(rows) == 1
    assert rows[0].topic_id == topic_id


@pytest.mark.asyncio
async def test_prebuilder_noop_without_provider(db, fake_redis, tmp_path: Path) -> None:
    user_id = "u_a"
    topic_id = "security.iam"
    await _seed(db, user_id, topic_id)

    set_bundle_source_provider(None)
    set_export_agent(None)
    event = TopicMastered(user_id=user_id, topic_id=topic_id, mastery=0.9)
    await dispatch_event(event, db=db, redis=fake_redis)

    rows = (
        await db.execute(orm.Artefact.__table__.select().where(orm.Artefact.user_id == user_id))
    ).all()
    assert rows == []


@pytest.mark.asyncio
async def test_prebuilder_provider_can_skip(db, fake_redis, tmp_path: Path) -> None:
    user_id = "u_a"
    topic_id = "billing.pricing"
    await _seed(db, user_id, topic_id)

    async def provider(_uid: str, _tid: str) -> BundleSource | None:
        return None  # explicit skip

    set_bundle_source_provider(provider)
    try:
        event = TopicMastered(user_id=user_id, topic_id=topic_id, mastery=0.9)
        await dispatch_event(event, db=db, redis=fake_redis)
    finally:
        set_bundle_source_provider(None)

    rows = (
        await db.execute(orm.Artefact.__table__.select().where(orm.Artefact.user_id == user_id))
    ).all()
    assert rows == []
