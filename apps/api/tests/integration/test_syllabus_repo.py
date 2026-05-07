"""M-1: SyllabusRepo writes and reads back the topic tree."""

from __future__ import annotations

import pytest
from api.db.repositories import ExamRepo, SyllabusRepo
from shared.models import SyllabusTopic


@pytest.mark.asyncio
async def test_replace_then_fetch_round_trip(db) -> None:
    await ExamRepo(db).upsert("aws-ccp", "AWS CCP", "aws-ccp")
    tree = [
        SyllabusTopic(
            id="cloud",
            exam_id="aws-ccp",
            title="Cloud Concepts",
            weight=0.5,
            children=[
                SyllabusTopic(
                    id="cloud.benefits",
                    exam_id="aws-ccp",
                    parent_id="cloud",
                    title="Benefits",
                    weight=0.2,
                ),
                SyllabusTopic(
                    id="cloud.economics",
                    exam_id="aws-ccp",
                    parent_id="cloud",
                    title="Economics",
                    weight=0.3,
                ),
            ],
        )
    ]

    count = await SyllabusRepo(db).replace_for_exam("aws-ccp", tree)
    assert count == 3

    fetched = await SyllabusRepo(db).fetch_tree("aws-ccp")
    assert len(fetched) == 1
    root = fetched[0]
    assert root.id == "cloud"
    assert {c.id for c in root.children} == {"cloud.benefits", "cloud.economics"}


@pytest.mark.asyncio
async def test_replace_overwrites_existing(db) -> None:
    await ExamRepo(db).upsert("aws-ccp", "AWS CCP", "aws-ccp")

    first = [SyllabusTopic(id="a", exam_id="aws-ccp", title="Old", weight=1.0)]
    await SyllabusRepo(db).replace_for_exam("aws-ccp", first)

    second = [SyllabusTopic(id="b", exam_id="aws-ccp", title="New", weight=1.0)]
    await SyllabusRepo(db).replace_for_exam("aws-ccp", second)

    tree = await SyllabusRepo(db).fetch_tree("aws-ccp")
    assert {n.id for n in tree} == {"b"}
