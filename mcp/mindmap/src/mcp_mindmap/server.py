"""MCP server exposing the mind-map renderer as a tool.

Run via:
    python -m mcp_mindmap.server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_mindmap.render import to_mermaid, to_svg

mcp_server = FastMCP("mindmap")


@mcp_server.tool()
def render_mindmap(node: dict[str, Any]) -> dict[str, Any]:
    """Render a node tree as Mermaid text + an inline SVG.

    Input shape::
        {"text": "Cloud", "children": [{"text": "Compute", "children": [...]}, ...]}

    The output bundles both formats so callers can pick what fits.
    """
    return {
        "mermaid": to_mermaid(node),
        "svg": to_svg(node),
    }


def main() -> None:
    mcp_server.run()


if __name__ == "__main__":
    main()
