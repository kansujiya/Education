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


def _build_questions_input(user_message: str) -> dict[str, Any]:
    """Three deterministic comprehension questions with rubrics.

    Key points are seeded with a sentinel string per question so the
    judge fake (below) can return correct/incorrect deterministically
    based on whether the learner answer mentions the sentinel.
    """
    return {
        "questions": [
            {
                "text": "What is the core idea?",
                "model_answer": "The cloud is rented capacity.",
                "key_points": ["rented capacity", "pay-as-you-go"],
            },
            {
                "text": "Name one benefit and one trade-off.",
                "model_answer": "Elasticity is a benefit; vendor lock-in is a trade-off.",
                "key_points": ["elasticity", "trade-off"],
            },
            {
                "text": "Give one concrete example from the lesson.",
                "model_answer": "EC2 lets you rent a VM by the hour.",
                "key_points": ["example", "EC2"],
            },
        ]
    }


def _build_judgement_input(user_message: str) -> dict[str, Any]:
    """Deterministic grading: correct iff the learner's answer mentions
    at least one key point.

    The fake parses ``# Key Points`` and ``# Learner Answer`` from the
    prompt the agent sends.
    """
    key_points = _extract_section(user_message, "# Key Points")
    learner = _extract_section(user_message, "# Learner Answer").lower()
    points = [
        line.lstrip("- ").strip().lower()
        for line in key_points.splitlines()
        if line.strip().startswith("-")
    ]
    if not points:
        return {"score": 0.5, "correct": False, "gap": "no key points provided"}
    hits = [p for p in points if p and p in learner]
    if hits:
        return {"score": 1.0, "correct": True, "gap": ""}
    return {"score": 0.3, "correct": False, "gap": f"missing: {points[0]}"}


def _build_cards_input(user_message: str) -> dict[str, Any]:
    """Six deterministic cards (2 recall, 3 mcq, 1 short) with rubric key points.

    The same key-point trick used by the judge: a learner answer that
    mentions any key point is graded correct.
    """
    return {
        "cards": [
            {
                "type": "recall",
                "prompt": "Define pay-as-you-go in one line.",
                "answer": "You pay only for what you use; no upfront commitment.",
                "key_points": ["pay-as-you-go"],
                "source_pyq_id": "pyq_001",
                "source_year": 2023,
            },
            {
                "type": "recall",
                "prompt": "What does elasticity mean?",
                "answer": "Capacity scales up or down on demand.",
                "key_points": ["elasticity", "capacity"],
                "source_pyq_id": "pyq_001",
                "source_year": 2023,
            },
            {
                "type": "mcq",
                "prompt": (
                    "Which is most accurate? "
                    "A) cloud is free  B) cloud trades CapEx for OpEx  "
                    "C) cloud removes all responsibility  D) cloud needs no security"
                ),
                "answer": "B",
                "key_points": ["CapEx", "OpEx"],
                "source_pyq_id": "pyq_003",
                "source_year": 2024,
            },
            {
                "type": "mcq",
                "prompt": ("Which family is memory-optimised? A) M  B) C  C) R  D) T"),
                "answer": "C",
                "key_points": ["R family", "memory"],
                "source_pyq_id": "pyq_016",
                "source_year": 2023,
            },
            {
                "type": "mcq",
                "prompt": (
                    "Encryption at rest protects: "
                    "A) data on the wire  B) stored data  "
                    "C) the hypervisor  D) the network"
                ),
                "answer": "B",
                "key_points": ["at rest", "stored data"],
                "source_pyq_id": "pyq_014",
                "source_year": 2023,
            },
            {
                "type": "short",
                "prompt": "Why design for failure?",
                "answer": "Because any single component can fail; redundancy keeps the system available.",
                "key_points": ["redundancy", "fail"],
                "source_pyq_id": "pyq_005",
                "source_year": 2024,
            },
        ]
    }


def _build_tool_input(tool_name: str, user_message: str) -> dict[str, Any]:
    if tool_name == "submit_questions":
        return _build_questions_input(user_message)
    if tool_name in ("submit_judgement", "submit_card_judgement"):
        return _build_judgement_input(user_message)
    if tool_name == "submit_cards":
        return _build_cards_input(user_message)
    return _build_mindmap_input(user_message)


class FakeMessages:
    """Anthropic.messages stand-in with scripted behaviour driven by tool name:

    - ``submit_mindmap``  → 3-node tree with the topic title at the root.
    - ``submit_questions`` → 3 questions with rubrics seeded with sentinel keys.
    - ``submit_judgement`` → correct iff learner's answer mentions a key point.
    - no tool_choice → "lesson" text echoing the notes for groundedness checks.

    Streaming yields the lesson in 4 chunks.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        if kwargs.get("tool_choice"):
            tool_name = kwargs["tool_choice"]["name"]
            user_msg = kwargs["messages"][0]["content"]
            return _Message(
                content=[
                    _Block(
                        type="tool_use",
                        name=tool_name,
                        input=_build_tool_input(tool_name, user_msg),
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
