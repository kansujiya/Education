"""M-2 eval lock-in: Tutor lessons cite supplied notes (groundedness).

These run on a fake Anthropic client whose responses are constructed
from the prompt the agent sends, so the assertions are deterministic
and need no API key. Real-LLM evals can be layered in later.
"""

from __future__ import annotations

from pathlib import Path

from api.agents import TutorAgent
from api.rag import NotesIndex

REPO = Path(__file__).resolve().parents[4]
NOTES = REPO / "seeds" / "notes_aws_ccp.jsonl"


def test_lesson_includes_excerpt_from_retrieved_notes(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)

    result = tutor.teach(
        topic_id="security.shared-resp",
        topic_title="Shared Responsibility Model",
    )

    # The fake constructs a lesson out of the supplied notes; we assert
    # the lesson body references at least one phrase from a retrieved chunk.
    assert result.notes_used, "no notes retrieved for this topic"
    chunk_phrases = [c.chunk.chunk[:30] for c in result.notes_used]
    assert any(phrase[:15] in result.lesson_md for phrase in chunk_phrases), (
        "lesson did not echo any retrieved chunk"
    )


def test_lesson_emits_three_line_summary(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    result = tutor.teach(
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits of the Cloud",
    )
    assert "Summary:" in result.lesson_md
    # Count numbered summary lines.
    lines = [
        ln.strip()
        for ln in result.lesson_md.splitlines()
        if ln.strip().startswith(("1.", "2.", "3."))
    ]
    assert len(lines) >= 3


def test_mindmap_extracted_via_tool_use(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    result = tutor.teach(
        topic_id="technology.compute",
        topic_title="Compute Services",
    )
    assert "text" in result.mindmap_nodes
    assert isinstance(result.mindmap_nodes.get("children"), list)


def test_streams_chunks_in_order(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    captured: list[str] = []
    result = tutor.teach(
        topic_id="cloud-concepts.benefits",
        topic_title="Benefits of the Cloud",
        on_chunk=captured.append,
    )
    assert "".join(captured) == result.lesson_md
    assert len(captured) >= 2  # multiple chunks streamed


def test_provenance_visible_to_caller(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    chunks_iter, retrieved = tutor.stream_lesson(
        topic_id="security.iam",
        topic_title="IAM and Access Control",
    )
    list(chunks_iter)  # exhaust
    assert retrieved
    assert all(r.chunk.source for r in retrieved)
