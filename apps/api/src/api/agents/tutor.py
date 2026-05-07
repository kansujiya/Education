"""Tutor agent: layman lesson + mind-map structure for one topic.

Pattern: **prompt chaining**.
  1. Stream a lesson in plain English using retrieved notes as context.
  2. Run a small structured-output call to extract a mind-map node tree
     from the (now generated) lesson.

The mind-map *rendering* (Mermaid + SVG) belongs to ``mcp-mindmap`` and
is invoked by the caller (e.g. the CLI) once the structure is in hand.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from shared.models import LANGUAGE_NAMES, Language

from api.agent.anthropic_client import ToolDefinition
from api.agent.base import BaseAgent
from api.config import settings
from api.rag import NotesIndex, RetrievedChunk

LESSON_SYSTEM = """\
You are a patient tutor for exam preparation. Teach the given topic in
**plain, layman language** for a {level} learner.

**Output language:** {language_name}.
- Write the entire lesson — intuition, analogy, body, summary — in {language_name}.
- Keep technical terms that are universally used in English (e.g. "IAM", "EC2", "VPC")
  in English even when the rest is in another language. Do not translate proper
  nouns, product names, or acronyms.
- Source labels (e.g. "source: AWS Whitepaper") stay in English.

Always:
- Open with a one-sentence intuition.
- Use a concrete analogy from everyday life.
- Tie the explanation to the supplied notes; do not invent facts that
  contradict them.
- Cite the source after any fact you draw from the notes, e.g.
  ``(source: AWS Whitepaper)``.
- Close with a 3-line summary.

Keep it under ~350 words.
"""

MINDMAP_SYSTEM = """\
You build mind-map node trees from short lessons. Output **only** by
calling the ``submit_mindmap`` tool. The tree is at most 3 levels deep.
Each node has 2-5 children when it has any. Keep node text under 6 words.

**Node-text language:** {language_name}. Mirror the lesson's language. Keep
universal technical terms (IAM, EC2, S3, ...) in English regardless.
"""

MINDMAP_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "node": {
            "type": "object",
            "description": "Root node. Recursive: each node has text and children.",
            "properties": {
                "text": {"type": "string"},
                "children": {
                    "type": "array",
                    "items": {"$ref": "#/properties/node"},
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        }
    },
    "required": ["node"],
    "additionalProperties": False,
}


def _format_notes(notes: list[RetrievedChunk]) -> str:
    if not notes:
        return "(no relevant notes retrieved)"
    lines = []
    for r in notes:
        lines.append(f"- ({r.chunk.source}) {r.chunk.chunk}")
    return "\n".join(lines)


@dataclass(slots=True)
class TutorResult:
    topic_id: str
    topic_title: str
    lesson_md: str
    mindmap_nodes: dict[str, Any]
    notes_used: list[RetrievedChunk]


class TutorAgent:
    """Two-call agent: stream the lesson, then extract a mind-map tree."""

    def __init__(
        self,
        client: Any,
        notes: NotesIndex,
        *,
        lesson_model: str | None = None,
        mindmap_model: str | None = None,
    ) -> None:
        self._client = client
        self._notes = notes
        self._lesson_model = lesson_model or settings.default_model
        self._mindmap_model = mindmap_model or settings.high_volume_model

    def _build_user_prompt(self, topic_title: str, retrieved: list[RetrievedChunk]) -> str:
        return (
            f"# Topic\n{topic_title}\n\n"
            f"# Notes (use these; cite the source)\n{_format_notes(retrieved)}\n\n"
            "Teach me this topic now."
        )

    def _retrieve_with_fallback(
        self, topic_id: str, topic_title: str, k: int
    ) -> list[RetrievedChunk]:
        # Prefer notes scoped to the requested topic.
        scoped = self._notes.search(topic_title, k=k, topic_id=topic_id)
        if scoped:
            return scoped
        # Fall back to a global keyword query so we don't ground on nothing.
        return self._notes.search(topic_title, k=k)

    def stream_lesson(
        self,
        topic_id: str,
        topic_title: str,
        *,
        level: str = "novice",
        language: Language = "en",
        k: int = 5,
    ) -> tuple[Iterator[str], list[RetrievedChunk]]:
        """Return (chunk-iterator, notes_used).

        The caller streams the iterator to the user; ``notes_used`` is
        already known, so callers can render provenance immediately.
        """
        retrieved = self._retrieve_with_fallback(topic_id, topic_title, k)
        agent = BaseAgent(
            name="tutor.lesson",
            system_prompt=LESSON_SYSTEM.format(level=level, language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._lesson_model,
            max_tokens=1500,
        )
        user_prompt = self._build_user_prompt(topic_title, retrieved)
        return agent.stream(user_prompt), retrieved

    def extract_mindmap(
        self,
        topic_title: str,
        lesson_md: str,
        *,
        language: Language = "en",
    ) -> dict[str, Any]:
        agent = BaseAgent(
            name="tutor.mindmap",
            system_prompt=MINDMAP_SYSTEM.format(language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._mindmap_model,
            max_tokens=600,
            tools=[
                ToolDefinition(
                    name="submit_mindmap",
                    description="Submit the mind-map tree for the lesson.",
                    input_schema=MINDMAP_TOOL_INPUT_SCHEMA,
                )
            ],
        )
        user = f"# Topic\n{topic_title}\n\n# Lesson\n{lesson_md}\n\nProduce the mind-map."
        result = agent.run(user, force_tool="submit_mindmap")
        if result.tool_use is None:
            raise RuntimeError("mindmap agent did not call submit_mindmap")
        node = result.tool_use["input"]
        if not isinstance(node, dict) or "node" not in node:
            raise RuntimeError(f"unexpected mindmap tool input: {node!r}")
        inner = node["node"]
        if not isinstance(inner, dict):
            raise RuntimeError(f"unexpected mindmap node payload: {inner!r}")
        return inner

    def teach(
        self,
        topic_id: str,
        topic_title: str,
        *,
        level: str = "novice",
        language: Language = "en",
        k: int = 5,
        on_chunk: object = None,
    ) -> TutorResult:
        """End-to-end: stream lesson (calling ``on_chunk`` per delta), then
        extract the mind-map structure.

        Returns the assembled ``TutorResult``. If ``on_chunk`` is
        ``None`` the caller still gets the full text in the result.
        """
        chunks_iter, retrieved = self.stream_lesson(
            topic_id, topic_title, level=level, language=language, k=k
        )
        parts: list[str] = []
        for chunk in chunks_iter:
            parts.append(chunk)
            if callable(on_chunk):
                on_chunk(chunk)
        lesson_md = "".join(parts)
        mindmap_nodes = self.extract_mindmap(topic_title, lesson_md, language=language)
        return TutorResult(
            topic_id=topic_id,
            topic_title=topic_title,
            lesson_md=lesson_md,
            mindmap_nodes=mindmap_nodes,
            notes_used=retrieved,
        )


class _TutorOutputModel(BaseModel):
    """Schema published for documentation; not used at runtime."""

    lesson_md: str
    mindmap_nodes: dict[str, Any]
