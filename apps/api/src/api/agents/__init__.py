"""Concrete agents (Tutor, Examiner, ...). Each = system prompt + tools + model."""

from api.agents.examiner import ExaminerAgent
from api.agents.loop import (
    GetAnswer,
    IterationLog,
    LoopResult,
    QAExchange,
    TutorExaminerLoop,
)
from api.agents.tutor import TutorAgent, TutorResult

__all__ = [
    "ExaminerAgent",
    "GetAnswer",
    "IterationLog",
    "LoopResult",
    "QAExchange",
    "TutorAgent",
    "TutorExaminerLoop",
    "TutorResult",
]
