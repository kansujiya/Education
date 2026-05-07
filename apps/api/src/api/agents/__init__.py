"""Concrete agents (Tutor, Examiner, Assessor, ...). Each = system prompt + tools + model."""

from api.agents.assessor import AssessorAgent, CardSpec
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
    "AssessorAgent",
    "CardSpec",
    "ExaminerAgent",
    "GetAnswer",
    "IterationLog",
    "LoopResult",
    "QAExchange",
    "TutorAgent",
    "TutorExaminerLoop",
    "TutorResult",
]
