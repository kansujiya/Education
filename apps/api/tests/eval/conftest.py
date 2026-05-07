"""Eval-suite fixtures — a fake Anthropic client whose lesson responses
echo the supplied notes so groundedness assertions are deterministic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class _Block:
    text: str = ""
    type: str = "text"
    name: str = ""
    input: dict[str, Any] | None = None


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _Message:
    content: list[_Block]
    usage: _Usage = field(default_factory=_Usage)


class _Stream:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream: Iterator[str] = iter(chunks)

    def __enter__(self) -> _Stream:
        return self

    def __exit__(self, *_: Any) -> None:
        return None


def _format_lesson_from_user_msg(user_message: str) -> str:
    """Build a deterministic 'lesson' that echoes notes the prompt carries.

    We prefix with an analogy and end with a 3-line summary so we can
    assert the structure without a real LLM. The body lifts noun phrases
    from the supplied notes section so groundedness checks pass.
    """
    notes_section = _extract_section(user_message, "# Notes")
    excerpt = " ".join(notes_section.splitlines()[:6]) if notes_section else ""
    return (
        "Imagine renting a kitchen by the hour instead of building one — that is the cloud.\n\n"
        f"Based on the supplied notes: {excerpt}\n\n"
        "Summary:\n"
        "1. Pay only for what you use.\n"
        "2. Scale up or down on demand.\n"
        "3. Reach customers globally without owning hardware.\n"
    )


def _extract_section(text: str, header: str) -> str:
    """Crude markdown-section extractor used only for the fake."""
    out: list[str] = []
    started = False
    for line in text.splitlines():
        if line.strip().startswith(header):
            started = True
            continue
        if started and line.startswith("# "):
            break
        if started:
            out.append(line)
    return "\n".join(out).strip()


def _build_mindmap_input(user_message: str) -> dict[str, Any]:
    """Pull a topic title from the prompt and return a small mind-map tree."""
    title = "Topic"
    for line in user_message.splitlines():
        line = line.strip()
        if line.startswith("# Topic"):
            continue
        if line:
            title = line
            break
    return {
        "node": {
            "text": title,
            "children": [
                {"text": "Idea 1", "children": [{"text": "Detail A"}]},
                {"text": "Idea 2", "children": [{"text": "Detail B"}]},
                {"text": "Summary"},
            ],
        }
    }


class FakeMessages:
    """Anthropic.messages stand-in with two scripted modes:

    - tool_choice present → return a tool_use block with a built mind-map.
    - otherwise → return a 'lesson' text echoing the notes from the prompt.

    Streaming yields the lesson in 4 chunks.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        if kwargs.get("tool_choice"):
            user_msg = kwargs["messages"][0]["content"]
            return _Message(
                content=[
                    _Block(
                        type="tool_use",
                        name=kwargs["tool_choice"]["name"],
                        input=_build_mindmap_input(user_msg),
                    )
                ],
                usage=_Usage(input_tokens=200, output_tokens=80),
            )
        user_msg = kwargs["messages"][0]["content"]
        text = _format_lesson_from_user_msg(user_msg)
        return _Message(
            content=[_Block(text=text)],
            usage=_Usage(input_tokens=300, output_tokens=180),
        )

    @contextmanager
    def stream(self, **kwargs: Any) -> Iterator[_Stream]:
        self.stream_calls.append(kwargs)
        user_msg = kwargs["messages"][0]["content"]
        text = _format_lesson_from_user_msg(user_msg)
        # split into ~4 chunks for streaming feel.
        n = max(1, len(text) // 4)
        chunks = [text[i : i + n] for i in range(0, len(text), n)]
        with _Stream(chunks) as s:
            yield s


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


@pytest.fixture
def fake_anthropic_eval() -> FakeAnthropic:
    return FakeAnthropic()
