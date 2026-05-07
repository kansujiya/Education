"""Thin wrapper around the Anthropic SDK with prompt-cache plumbing.

Centralising this lets every agent get prompt caching and usage parsing
for free, and makes it trivial to swap in a fake client for tests.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from shared.tracing import AgentRunResult, TokenUsage


class _MessagesAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _AnthropicLike(Protocol):
    @property
    def messages(self) -> _MessagesAPI: ...


@dataclass(slots=True)
class ToolDefinition:
    """A tool the LLM can call. ``input_schema`` is a JSON-Schema dict."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class CompletionRequest:
    """Input shape we hand to the wrapper. Decoupled from the SDK."""

    model: str
    system_prompt: str
    user_message: str
    max_tokens: int = 1024
    cache_system: bool = True
    tools: list[ToolDefinition] | None = None
    force_tool: str | None = None


def _system_blocks(system_prompt: str, cache: bool) -> list[dict[str, Any]] | str:
    """Format the system prompt as cache-controlled blocks when caching is on.

    Anthropic accepts either a plain string or a list of typed blocks. We
    use blocks only when caching to keep the wire format simple otherwise.
    """
    if not cache:
        return system_prompt
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _parse_usage(model: str, raw: Any) -> TokenUsage:
    return TokenUsage(
        model=model,
        input_tokens=getattr(raw, "input_tokens", 0) or 0,
        output_tokens=getattr(raw, "output_tokens", 0) or 0,
        cache_read_input_tokens=getattr(raw, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(raw, "cache_creation_input_tokens", 0) or 0,
    )


def _extract_text(content: Any) -> str:
    """Anthropic responses ship a list of content blocks; concatenate text blocks."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _extract_tool_use(content: Any) -> dict[str, object] | None:
    """Return ``{"name": ..., "input": ...}`` for the first tool_use block, or None."""
    for block in content or []:
        if getattr(block, "type", None) == "tool_use":
            name = getattr(block, "name", None)
            tool_input = getattr(block, "input", None)
            if isinstance(name, str):
                return {"name": name, "input": tool_input}
    return None


def _serialise_tools(tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


class AnthropicWrapper:
    """Wraps an Anthropic SDK client, adding cache + usage parsing.

    The client is injected so tests can pass a Mock without touching the
    network or needing an API key.
    """

    def __init__(self, client: _AnthropicLike) -> None:
        self._client = client

    def complete(self, req: CompletionRequest) -> AgentRunResult:
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "system": _system_blocks(req.system_prompt, req.cache_system),
            "messages": [{"role": "user", "content": req.user_message}],
        }
        serialised_tools = _serialise_tools(req.tools)
        if serialised_tools is not None:
            kwargs["tools"] = serialised_tools
        if req.force_tool:
            kwargs["tool_choice"] = {"type": "tool", "name": req.force_tool}
        response = self._client.messages.create(**kwargs)
        duration_ms = int((time.perf_counter() - started) * 1000)
        content = getattr(response, "content", "")
        return AgentRunResult(
            text=_extract_text(content),
            tool_use=_extract_tool_use(content),
            usage=_parse_usage(req.model, getattr(response, "usage", object())),
            duration_ms=duration_ms,
        )

    def stream(self, req: CompletionRequest) -> Iterator[str]:
        """Yield text deltas as they arrive.

        Final usage is not exposed by this iterator; for full result use
        ``complete`` once streaming finishes if you need accounting.
        """
        with self._client.messages.stream(  # type: ignore[attr-defined]
            model=req.model,
            max_tokens=req.max_tokens,
            system=_system_blocks(req.system_prompt, req.cache_system),
            messages=[{"role": "user", "content": req.user_message}],
        ) as stream:
            yield from stream.text_stream
