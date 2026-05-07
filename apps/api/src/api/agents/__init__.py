"""Concrete agents (Tutor, Examiner, Assessor, ...). Each = system prompt + tools + model."""

from api.agents.assessor import AssessorAgent, CardSpec
from api.agents.coach import CoachAgent, PlanResult
from api.agents.examiner import ExaminerAgent
from api.agents.loop import (
    GetAnswer,
    IterationLog,
    LoopResult,
    QAExchange,
    TutorExaminerLoop,
)
from api.agents.onboarding import OnboardingAgent, OnboardingResult
from api.agents.tutor import TutorAgent, TutorResult

__all__ = [
    "AssessorAgent",
    "CardSpec",
    "CoachAgent",
    "ExaminerAgent",
    "GetAnswer",
    "IterationLog",
    "LoopResult",
    "OnboardingAgent",
    "OnboardingResult",
    "PlanResult",
    "QAExchange",
    "TutorAgent",
    "TutorExaminerLoop",
    "TutorResult",
]
