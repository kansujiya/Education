"""M-2 demo lock-in: mcp-mindmap stdio round-trip returns valid SVG."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from api.mcp import MCPClient, MCPServerSpec


@pytest.fixture
def mindmap_spec() -> MCPServerSpec:
    return MCPServerSpec(
        command="python",
        args=["-m", "mcp_mindmap.server"],
        env=os.environ.copy(),
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_render_mindmap_round_trip(mindmap_spec) -> None:
    node = {
        "text": "Cloud",
        "children": [
            {"text": "Compute", "children": [{"text": "EC2"}, {"text": "Lambda"}]},
            {"text": "Storage", "children": [{"text": "S3"}]},
        ],
    }
    out = await MCPClient(mindmap_spec).call("render_mindmap", {"node": node})

    assert isinstance(out, dict)
    assert "mermaid" in out and "svg" in out
    assert out["mermaid"].startswith("mindmap")

    root = ET.fromstring(out["svg"])
    assert root.tag.endswith("}svg") or root.tag == "svg"
    # Spot-check labels rendered in SVG.
    assert "Compute" in out["svg"]
    assert "EC2" in out["svg"]
