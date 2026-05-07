"""MCP server exposing the bundle assembler.

Returns the bundle bytes **base64-encoded** because MCP tool responses
are JSON. Callers (the ExportAgent) decode and write the bytes to the
configured Storage.

Run via:
    python -m mcp_pdf.server
"""

from __future__ import annotations

import base64
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_pdf.bundle import build_zip

mcp_server = FastMCP("pdf")


@mcp_server.tool()
def bundle_markdown_zip(
    topic_id: str,
    topic_title: str,
    lesson_md: str,
    mindmap_svg: str,
    mindmap_mermaid: str,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the downloadable bundle and return base64 bytes + size."""
    raw = build_zip(
        topic_id=topic_id,
        topic_title=topic_title,
        lesson_md=lesson_md,
        mindmap_svg=mindmap_svg,
        mindmap_mermaid=mindmap_mermaid,
        cards=cards,
    )
    return {
        "format": "zip",
        "size_bytes": len(raw),
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def main() -> None:
    mcp_server.run()


if __name__ == "__main__":
    main()
