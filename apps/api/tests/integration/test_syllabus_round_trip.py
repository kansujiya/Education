"""M-1 demo lock-in: full MCP-stdio round-trip + DB write.

This test actually spawns ``python -m mcp_syllabus.server`` as a
subprocess, calls ``fetch_syllabus`` over stdio, and writes the result
through the repos. If this passes, the M-1 demo works end-to-end.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from api.db.repositories import SyllabusRepo
from api.loaders.syllabus import SyllabusLoader
from api.mcp import MCPClient, MCPServerSpec

REPO = Path(__file__).resolve().parents[4]


@pytest.fixture
def mcp_spec() -> MCPServerSpec:
    """Spawn the syllabus MCP server with seeds dir pointed at the repo's seeds/."""
    env = os.environ.copy()
    env["MCP_SYLLABUS_DATA_DIR"] = str(REPO / "seeds")
    return MCPServerSpec(
        command="python",
        args=["-m", "mcp_syllabus.server"],
        env=env,
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_fetch_and_parse_round_trip(db, mcp_spec) -> None:
    loader = SyllabusLoader(MCPClient(mcp_spec))

    result = await loader.load(db, "aws-ccp")

    assert result.exam_id == "aws-ccp"
    assert result.name == "AWS Certified Cloud Practitioner"
    assert result.topic_count > 0

    tree = await SyllabusRepo(db).fetch_tree("aws-ccp")
    titles = {t.title for t in tree}
    assert {
        "Cloud Concepts",
        "Security and Compliance",
        "Cloud Technology and Services",
        "Billing, Pricing and Support",
    }.issubset(titles)
