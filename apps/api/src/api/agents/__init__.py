"""Concrete agents (Tutor, Examiner, Assessor, Insight, Export, ...).

Each agent = system prompt + tools + model (or, for Coach/Insight/Export,
a thin orchestrator over deterministic helpers + MCP servers).
"""

from api.agents.assessor import AssessorAgent, CardSpec
from api.agents.coach import CoachAgent, PlanResult
from api.agents.examiner import ExaminerAgent
from api.agents.export import ExportAgent, ExportResult
from api.agents.insight import (
    InsightAgent,
    InsightPanel,
    MissingProvenanceError,
)
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
    "ExportAgent",
    "ExportResult",
    "GetAnswer",
    "InsightAgent",
    "InsightPanel",
    "IterationLog",
    "LoopResult",
    "MissingProvenanceError",
    "OnboardingAgent",
    "OnboardingResult",
    "PlanResult",
    "QAExchange",
    "TutorAgent",
    "TutorExaminerLoop",
    "TutorResult",
]
