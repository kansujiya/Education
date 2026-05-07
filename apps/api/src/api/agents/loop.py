"""Tutor + Examiner evaluator-optimiser loop.

The canonical M-3 flow:

  for iteration in 1..max_iterations:
      Tutor streams a lesson (re-teaching with prior gaps after iter 1).
      Examiner asks N comprehension questions.
      The caller (CLI / API) collects answers via ``get_answer``.
      Examiner judges each answer.
      if all correct and avg score >= pass_threshold:
          emit topic.understood; return PASS.
      else:
          gather gaps, loop.
  emit topic.misunderstood; return FAIL.

Events flow through ``api.bus.events.emit_event`` so the same listeners
that drive progress and SR scheduling (M-4) wire up automatically.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from redis.asyncio import Redis
from shared.events import TopicMisunderstood, TopicTaught, TopicUnderstood
from shared.models import Language
from shared.tools import Judgement, Question
from sqlalchemy.ext.asyncio import AsyncSession

from api.agents.examiner import ExaminerAgent
from api.agents.tutor import TutorAgent
from api.bus.events import emit_event


@dataclass(slots=True)
class QAExchange:
    """One question + answer + the Examiner's verdict for this iteration."""

    question: Question
    answer: str
    judgement: Judgement


@dataclass(slots=True)
class IterationLog:
    """Everything that happened in one teach→ask→judge cycle."""

    index: int
    lesson_md: str
    exchanges: list[QAExchange]
    avg_score: float
    passed: bool


@dataclass(slots=True)
class LoopResult:
    passed: bool
    iterations: int
    final_score: float
    log: list[IterationLog] = field(default_factory=list)
    last_gap: str = ""


# (question, q_index_in_iter, iter_index) -> answer_text
GetAnswer = Callable[[Question, int, int], Awaitable[str] | str]


class TutorExaminerLoop:
    """Composes Tutor + Examiner into the evaluator-optimiser loop."""

    def __init__(
        self,
        tutor: TutorAgent,
        examiner: ExaminerAgent,
        *,
        max_iterations: int = 3,
        pass_threshold: float = 0.7,
        n_questions: int = 3,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self._tutor = tutor
        self._examiner = examiner
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self.n_questions = n_questions

    async def run(
        self,
        topic_id: str,
        topic_title: str,
        *,
        user_id: str,
        get_answer: GetAnswer,
        language: Language = "en",
        level: str = "novice",
        on_lesson_chunk: Callable[[str], None] | None = None,
        on_question: Callable[[Question, int, int], None] | None = None,
        on_judgement: Callable[[Question, str, Judgement], None] | None = None,
        redis: Redis | None = None,
        db: AsyncSession | None = None,
    ) -> LoopResult:
        log: list[IterationLog] = []
        last_gap = ""
        for i in range(self.max_iterations):
            previous_gap = last_gap or None
            chunks_iter, _ = self._tutor.stream_lesson(
                topic_id,
                topic_title,
                level=level,
                language=language,
                previous_gap=previous_gap,
            )
            parts: list[str] = []
            for chunk in chunks_iter:
                parts.append(chunk)
                if on_lesson_chunk is not None:
                    on_lesson_chunk(chunk)
            lesson_md = "".join(parts)

            await emit_event(
                TopicTaught(user_id=user_id, topic_id=topic_id),
                redis=redis,
                db=db,
            )

            questions = self._examiner.ask_questions(
                topic_title, lesson_md, n=self.n_questions, language=language
            )
            exchanges: list[QAExchange] = []
            for idx, question in enumerate(questions):
                if on_question is not None:
                    on_question(question, idx, i)
                raw = get_answer(question, idx, i)
                if inspect.isawaitable(raw):
                    answer = await raw
                else:
                    answer = raw
                judgement = self._examiner.judge_answer(question, str(answer), language=language)
                if on_judgement is not None:
                    on_judgement(question, str(answer), judgement)
                exchanges.append(
                    QAExchange(question=question, answer=str(answer), judgement=judgement)
                )

            avg = sum(e.judgement.score for e in exchanges) / max(len(exchanges), 1)
            all_correct = bool(exchanges) and all(e.judgement.correct for e in exchanges)
            passed = all_correct and avg >= self.pass_threshold

            log.append(
                IterationLog(
                    index=i,
                    lesson_md=lesson_md,
                    exchanges=exchanges,
                    avg_score=avg,
                    passed=passed,
                )
            )

            if passed:
                await emit_event(
                    TopicUnderstood(user_id=user_id, topic_id=topic_id, score=avg),
                    redis=redis,
                    db=db,
                )
                return LoopResult(passed=True, iterations=i + 1, final_score=avg, log=log)

            gaps = [e.judgement.gap for e in exchanges if e.judgement.gap]
            last_gap = "; ".join(gaps) if gaps else last_gap

        # All iterations exhausted without passing.
        await emit_event(
            TopicMisunderstood(user_id=user_id, topic_id=topic_id, gap=last_gap or "n/a"),
            redis=redis,
            db=db,
        )
        return LoopResult(
            passed=False,
            iterations=self.max_iterations,
            final_score=log[-1].avg_score if log else 0.0,
            log=log,
            last_gap=last_gap,
        )


__all__: list[str] = [
    "GetAnswer",
    "IterationLog",
    "LoopResult",
    "QAExchange",
    "TutorExaminerLoop",
]
