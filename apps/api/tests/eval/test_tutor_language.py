"""M-2: language preference flows into the Tutor's system prompts.

We don't translate text in tests; we assert the language directive
lands in the system prompt sent to Claude. The real translation is
the model's job at runtime.
"""

from __future__ import annotations

from pathlib import Path

from api.agents import TutorAgent
from api.rag import NotesIndex

REPO = Path(__file__).resolve().parents[4]
NOTES = REPO / "seeds" / "notes_aws_ccp.jsonl"


def _system_blocks_for(call: dict) -> str:
    """The wrapper sends ``system`` as a list of blocks. Concatenate them."""
    system = call.get("system")
    if isinstance(system, str):
        return system
    return "\n".join(b.get("text", "") for b in system or [])


def test_lesson_system_prompt_mentions_hindi(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    chunks_iter, _ = tutor.stream_lesson(
        topic_id="security.iam",
        topic_title="IAM and Access Control",
        language="hi",
    )
    list(chunks_iter)  # exhaust to drive the call

    streamed = fake_anthropic_eval.messages.stream_calls
    assert streamed, "expected a streaming call to Claude"
    sys_text = _system_blocks_for(streamed[-1])
    assert "Hindi" in sys_text
    # Universal acronyms must NOT be translated — the prompt says so.
    assert "IAM" in sys_text or "EC2" in sys_text


def test_lesson_system_prompt_defaults_to_english(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    chunks_iter, _ = tutor.stream_lesson(
        topic_id="security.iam",
        topic_title="IAM and Access Control",
    )
    list(chunks_iter)
    sys_text = _system_blocks_for(fake_anthropic_eval.messages.stream_calls[-1])
    assert "English" in sys_text
    assert "Hindi" not in sys_text


def test_mindmap_system_prompt_mirrors_language(fake_anthropic_eval) -> None:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    tutor.teach(
        topic_id="security.iam",
        topic_title="IAM and Access Control",
        language="hi",
    )
    # Last create() call is the mindmap one (it carried tool_choice).
    mindmap_calls = [c for c in fake_anthropic_eval.messages.calls if c.get("tool_choice")]
    assert mindmap_calls, "expected a mindmap tool-use call"
    sys_text = _system_blocks_for(mindmap_calls[-1])
    assert "Hindi" in sys_text
