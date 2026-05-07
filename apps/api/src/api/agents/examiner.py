"""Examiner agent: Socratic questions + judgement.

Pattern: **routing** (pass / fail) + (with the Tutor) **evaluator-optimiser**.
Two operations, both forced via tool-use so outputs stay structured:

  - ``ask_questions(topic, lesson) -> [Question, ...]``
  - ``judge_answer(question, answer) -> Judgement``

The pass/fail decision and the regeneration loop live in
``api.agents.loop.TutorExaminerLoop``, which composes Tutor + Examiner.
"""

from __future__ import annotations

from typing import Any

from shared.models import LANGUAGE_NAMES, Language
from shared.tools import Judgement, Question

from api.agent.anthropic_client import ToolDefinition
from api.agent.base import BaseAgent
from api.config import settings

ASK_SYSTEM = """\
You are an exam coach. Generate {n} short comprehension questions
that probe whether the learner has understood the lesson. Output
**only** by calling the ``submit_questions`` tool.

Rules:
- Each question must be answerable from the supplied lesson.
- Provide a model answer (one sentence) and 2-4 key points the
  learner's answer must touch.
- Avoid trivia; favour questions that test understanding.

**Output language:** {language_name}. Universal technical terms
(IAM, EC2, S3, ...) stay in English.
"""

ASK_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "model_answer": {"type": "string"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["text", "model_answer", "key_points"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """\
You grade a single learner answer. Output **only** by calling the
``submit_judgement`` tool.

Scoring rubric:
- 1.0 — answer hits all key points, with no factual errors.
- 0.7-0.9 — answer hits most key points but misses minor detail.
- 0.4-0.6 — answer hits one or two key points; partial understanding.
- 0.0-0.3 — answer is wrong, off-topic, or empty.

``correct`` is true iff score >= 0.7.
``gap`` is one short sentence naming what was missing. Leave empty
when correct.

**Output language for ``gap``:** {language_name}. Universal technical
terms stay in English.
"""

JUDGE_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "correct": {"type": "boolean"},
        "gap": {"type": "string"},
    },
    "required": ["score", "correct", "gap"],
    "additionalProperties": False,
}


class ExaminerAgent:
    """Two-operation Socratic agent."""

    def __init__(
        self,
        client: Any,
        *,
        ask_model: str | None = None,
        judge_model: str | None = None,
    ) -> None:
        self._client = client
        self._ask_model = ask_model or settings.judgement_model
        self._judge_model = judge_model or settings.high_volume_model

    def ask_questions(
        self,
        topic_title: str,
        lesson_md: str,
        *,
        n: int = 3,
        language: Language = "en",
    ) -> list[Question]:
        agent = BaseAgent(
            name="examiner.ask",
            system_prompt=ASK_SYSTEM.format(n=n, language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._ask_model,
            max_tokens=900,
            tools=[
                ToolDefinition(
                    name="submit_questions",
                    description="Submit the comprehension questions for the lesson.",
                    input_schema=ASK_TOOL_INPUT_SCHEMA,
                )
            ],
        )
        user = (
            f"# Topic\n{topic_title}\n\n"
            f"# Lesson\n{lesson_md}\n\n"
            f"Produce {n} comprehension questions."
        )
        result = agent.run(user, force_tool="submit_questions")
        if result.tool_use is None:
            raise RuntimeError("examiner did not call submit_questions")
        payload = result.tool_use["input"]
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected tool payload: {payload!r}")
        items = payload.get("questions") or []
        if not isinstance(items, list):
            raise RuntimeError(f"questions field is not a list: {items!r}")
        return [Question.model_validate(item) for item in items]

    def judge_answer(
        self,
        question: Question,
        answer: str,
        *,
        language: Language = "en",
    ) -> Judgement:
        agent = BaseAgent(
            name="examiner.judge",
            system_prompt=JUDGE_SYSTEM.format(language_name=LANGUAGE_NAMES[language]),
            client=self._client,
            model=self._judge_model,
            max_tokens=200,
            tools=[
                ToolDefinition(
                    name="submit_judgement",
                    description="Submit the judgement for the learner's answer.",
                    input_schema=JUDGE_TOOL_INPUT_SCHEMA,
                )
            ],
        )
        key_points = "\n".join(f"- {p}" for p in question.key_points) or "(none)"
        user = (
            f"# Question\n{question.text}\n\n"
            f"# Model Answer\n{question.model_answer}\n\n"
            f"# Key Points\n{key_points}\n\n"
            f"# Learner Answer\n{answer}\n\n"
            "Grade it."
        )
        result = agent.run(user, force_tool="submit_judgement")
        if result.tool_use is None:
            raise RuntimeError("examiner did not call submit_judgement")
        payload = result.tool_use["input"]
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected tool payload: {payload!r}")
        return Judgement.model_validate(payload)
