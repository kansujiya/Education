"""Thin async MCP-stdio client.

Spawns a Python MCP server as a subprocess, calls a named tool, and
returns the parsed JSON result. One client per logical connection.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from mcp import StdioServerParameters


@dataclass
class MCPServerSpec:
    """How to spawn an MCP server."""

    command: str = "python"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


class MCPClient:
    """Open one MCP session and call its tools.

    Use as an async context manager so the subprocess and pipes are
    cleaned up deterministically.
    """

    def __init__(self, spec: MCPServerSpec) -> None:
        self._spec = spec

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        params = StdioServerParameters(
            command=self._spec.command,
            args=self._spec.args,
            env=self._spec.env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call ``tool_name`` and return parsed JSON.

        FastMCP returns tool results as ``TextContent`` blocks containing
        a JSON string when the tool returns a dict. We parse that here so
        callers get plain Python objects.
        """
        async with self.session() as session:
            result = await session.call_tool(tool_name, arguments=arguments)
        if not result.content:
            return None
        first = result.content[0]
        text = getattr(first, "text", None)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
