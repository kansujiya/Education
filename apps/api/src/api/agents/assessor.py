"""Assessor agent: PYQ-grounded card issuance + grading.

Two operations, both forced via tool-use:

  - ``issue_cards(topic_title, lesson_md, pyqs) -> [CardSpec, ...]``
    Mix of recall / MCQ / short-answer; each cites a PYQ year/section.
  - ``grade_attempt(card, answer) -> Judgement``
    Uses the same rubric idea as the Examiner: correct iff the answer
    mentions a key point (deterministic in tests; LLM in prod).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from shared.models import LANGUAGE_NAMES, Language
from shared.tools import Judgement

from api.agent.anthropic_client import ToolDefinition
from api.agent.base import BaseAgent
from api.config import settings

CardType = Literal["recall", "mcq", "short"]


class CardSpec(BaseModel):
    """A card the Assessor produced — about to be persisted."""

    type: CardType
    prompt: str
    answer: str = Field(..., description="Model answer / correct option text.")
    key_points: list[str] = Field(default_factory=list)
    source_pyq_id: str | None = None
    source_year: int | None = None


ISSUE_SYSTEM = """\
You are an exam assessor. Build {n} flash-cards / MCQs grounded in the
provided past-year questions (PYQs). Output **only** by calling the
``submit_cards`` tool.

Rules:
- Mix card types: about 1/3 recall (free recall), 1/3 mcq (with 4
  options inline in ``prompt``: A) ... B) ... C) ... D) ...), 1/3 short.
- Cite the source PYQ id and year on every card you ground in one.
- Each card carries 2-4 ``key_points`` for grading.
- Answers and prompts must be answerable from the supplied lesson
  combined with the PYQs. Do not introduce facts that contradict them.

**Output language:** {language_name}. Universal technical terms (IAM,
EC2, S3, ...) stay in English.
"""

ISSUE_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["recall", "mcq", "short"]},
                    "prompt": {"type": "string"},
                    "answer": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "source_pyq_id": {"type": "string"},
                    "source_year": {"type": "integer"},
                },
                "required": ["type", "prompt", "answer", "key_points"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


GRADE_SYSTEM = """\
Grade a single card attempt. Output **only** by calling the
``submit_card_judgement`` tool.

Scoring rubric (same as the Examiner):
- 1.0 — answer hits all key points.
- 0.7-0.9 — most key points, minor miss.
- 0.4-0.6 — partial.
- 0.0-0.3 — wrong / off-topic / empty.
``correct`` is true iff score >= 0.7. ``gap`` is one short sentence
explaining the miss; empty when correct.

**Output language for ``gap``:** {language_name}.
"""

GRADE_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "correct": {"type": "boolean"},
        "gap": {"type": "string"},
    },
    "required": ["score", "correct", "gap"],
    "additionalProperties": False,
}


def _format_pyqs(pyqs: list[dict[str, Any]]) -> str:
    if not pyqs:
        return "(no PYQs available)"
    lines = []
    for p in pyqs:
        lines.append(
            f"- [{p.get('id')}] ({p.get('year')}) {p.get('stem')}\n"
            f"    answer: {p.get('model_answer')}\n"
            f"    key_points: {', '.join(p.get('key_points', []))}"
        )
    return "\n".join(lines)


class AssessorAgent:
    def __init__(
        self,
        client: Any,
        *,
        issue_model: str | None = None,
        grade_model: str | None = None,
    ) -> None:
        self._client = client
        self._issue_model = issue_model or settings.judgement_model
        self._grade_model = grade_model or settings.high_volume_model

    def issue_cards(
        self,
        topic_title: str,
        lesson_md: str,
        pyqs: list[dict[str, Any]],
        *,
        n: int = 6,
        language: Language = "en",
    ) -> list[CardSpec]:
        agent = BaseAgent(
            name="assessor.issue",
            system_prompt=ISSUE_SYSTEM.format(n=n, language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._issue_model,
            max_tokens=1500,
            tools=[
                ToolDefinition(
                    name="submit_cards",
                    description="Submit the deck of cards for the topic.",
                    input_schema=ISSUE_TOOL_INPUT_SCHEMA,
                )
            ],
        )
        user = (
            f"# Topic\n{topic_title}\n\n"
            f"# Lesson\n{lesson_md}\n\n"
            f"# PYQs\n{_format_pyqs(pyqs)}\n\n"
            f"Produce {n} cards."
        )
        result = agent.run(user, force_tool="submit_cards")
        if result.tool_use is None:
            raise RuntimeError("assessor did not call submit_cards")
        payload = result.tool_use["input"]
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected payload: {payload!r}")
        cards = payload.get("cards") or []
        if not isinstance(cards, list):
            raise RuntimeError(f"cards is not a list: {cards!r}")
        return [CardSpec.model_validate(c) for c in cards]

    def grade_attempt(
        self,
        card: CardSpec,
        answer: str,
        *,
        language: Language = "en",
    ) -> Judgement:
        agent = BaseAgent(
            name="assessor.grade",
            system_prompt=GRADE_SYSTEM.format(language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._grade_model,
            max_tokens=200,
            tools=[
                ToolDefinition(
                    name="submit_card_judgement",
                    description="Submit the judgement for the learner's card attempt.",
                    input_schema=GRADE_TOOL_INPUT_SCHEMA,
                )
            ],
        )
        key_points = "\n".join(f"- {p}" for p in card.key_points) or "(none)"
        user = (
            f"# Card type\n{card.type}\n\n"
            f"# Prompt\n{card.prompt}\n\n"
            f"# Model Answer\n{card.answer}\n\n"
            f"# Key Points\n{key_points}\n\n"
            f"# Learner Answer\n{answer}\n\n"
            "Grade it."
        )
        result = agent.run(user, force_tool="submit_card_judgement")
        if result.tool_use is None:
            raise RuntimeError("assessor did not call submit_card_judgement")
        payload = result.tool_use["input"]
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected payload: {payload!r}")
        return Judgement.model_validate(payload)
