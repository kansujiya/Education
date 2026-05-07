"""Shared fixtures: a fake Anthropic client that exercises the wrapper without
making any network calls.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class _FakeContentBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _FakeMessage:
    content: list[_FakeContentBlock]
    usage: _FakeUsage


class _FakeStream:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream: Iterator[str] = iter(chunks)

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *_: Any) -> None:
        return None


class FakeMessages:
    """Stand-in for Anthropic.messages with scriptable behaviour.

    Tests configure ``responses`` (for ``create``) and ``stream_chunks``
    (for ``stream``). Each ``create`` call advances through ``responses``;
    captured kwargs are exposed via ``calls`` for assertions.
    """

    def __init__(self) -> None:
        self.responses: list[_FakeMessage] = []
        self.stream_chunks: list[list[str]] = []
        self.calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    def queue(self, message: _FakeMessage) -> None:
        self.responses.append(message)

    def queue_stream(self, chunks: list[str]) -> None:
        self.stream_chunks.append(chunks)

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        if not self.responses:
            return _FakeMessage(content=[_FakeContentBlock(text="ok")], usage=_FakeUsage())
        return self.responses.pop(0)

    @contextmanager
    def stream(self, **kwargs: Any) -> Iterator[_FakeStream]:
        self.stream_calls.append(kwargs)
        chunks = self.stream_chunks.pop(0) if self.stream_chunks else ["ok"]
        with _FakeStream(chunks) as stream:
            yield stream


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


@pytest.fixture
def fake_anthropic() -> FakeAnthropic:
    return FakeAnthropic()


@pytest.fixture
def fake_message() -> Any:
    """Factory so tests can build canned responses inline."""

    def _make(
        text: str = "hello",
        input_tokens: int = 100,
        output_tokens: int = 50,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
    ) -> _FakeMessage:
        return _FakeMessage(
            content=[_FakeContentBlock(text=text)],
            usage=_FakeUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
            ),
        )

    return _make
