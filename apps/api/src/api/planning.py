"""Study-plan composition.

Pure function over (topics, PYQ frequencies, user progress, calendar) so
the Coach has a deterministic core that's easy to test and easy to swap.
The LLM-side reasoning (re-explaining the plan, picking analogies) wraps
this function — see ``api.agents.coach``.

Scoring formula
---------------

For each leaf topic::

    yield = pyq_frequency.get(topic_id, 0)        # past-paper signal
    need  = 1.0 - mastery                         # diminishing returns
    score = (yield + 0.5) * need

The ``+ 0.5`` floor keeps "no-PYQ-yet" topics in contention. ``need``
drops to zero once mastered, so progress automatically deprioritises
known topics on the next replan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from shared.models import SyllabusTopic

DEFAULT_DAYS_WINDOW = 7
DEFAULT_MINUTES_PER_TOPIC = 30


@dataclass(slots=True)
class TopicSlot:
    topic_id: str
    title: str
    minutes: int
    score: float


@dataclass(slots=True)
class DayPlan:
    date: str  # ISO date for clean JSON round-trip
    topics: list[TopicSlot] = field(default_factory=list)


@dataclass(slots=True)
class StudyPlan:
    user_id: str
    exam_id: str
    exam_date: str  # ISO date
    days_to_exam: int
    daily_minutes: int
    days: list[DayPlan]

    def total_minutes(self) -> int:
        return sum(t.minutes for d in self.days for t in d.topics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "exam_id": self.exam_id,
            "exam_date": self.exam_date,
            "days_to_exam": self.days_to_exam,
            "daily_minutes": self.daily_minutes,
            "days": [{"date": d.date, "topics": [asdict(t) for t in d.topics]} for d in self.days],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StudyPlan:
        return cls(
            user_id=str(data.get("user_id", "")),
            exam_id=str(data.get("exam_id", "")),
            exam_date=str(data.get("exam_date", "")),
            days_to_exam=int(data.get("days_to_exam", 0)),
            daily_minutes=int(data.get("daily_minutes", 0)),
            days=[
                DayPlan(
                    date=str(d.get("date", "")),
                    topics=[TopicSlot(**t) for t in d.get("topics", [])],
                )
                for d in data.get("days", [])
            ],
        )


def _flatten_leaves(roots: list[SyllabusTopic]) -> list[SyllabusTopic]:
    out: list[SyllabusTopic] = []
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node.children:
            stack.extend(node.children)
        else:
            out.append(node)
    return out


def compute_plan(
    *,
    user_id: str,
    exam_id: str,
    exam_date: datetime,
    daily_minutes: int,
    topics: list[SyllabusTopic],
    pyq_frequency: dict[str, int],
    progress: dict[str, float],
    days_window: int = DEFAULT_DAYS_WINDOW,
    minutes_per_topic: int = DEFAULT_MINUTES_PER_TOPIC,
    today: date | None = None,
) -> StudyPlan:
    """Build a StudyPlan covering the next ``days_window`` days (or fewer if
    the exam is sooner).
    """
    base_today = today or datetime.now().date()
    exam_day = exam_date.date() if isinstance(exam_date, datetime) else exam_date
    days_to_exam = max((exam_day - base_today).days, 1)
    days = max(min(days_window, days_to_exam), 1)
    topics_per_day = max(daily_minutes // minutes_per_topic, 1)
    slots = days * topics_per_day

    # Use only leaf topics — interior nodes are organisational headings.
    leaves = _flatten_leaves(topics)
    scored: list[tuple[float, SyllabusTopic]] = []
    for t in leaves:
        freq = float(pyq_frequency.get(t.id, 0))
        mastery = float(progress.get(t.id, 0.0))
        score = (freq + 0.5) * (1.0 - mastery)
        scored.append((score, t))
    scored.sort(key=lambda x: (x[0], x[1].title), reverse=True)
    chosen = scored[:slots]

    plan_days: list[DayPlan] = []
    for d in range(days):
        slots_today = chosen[d * topics_per_day : (d + 1) * topics_per_day]
        plan_days.append(
            DayPlan(
                date=(base_today + timedelta(days=d)).isoformat(),
                topics=[
                    TopicSlot(
                        topic_id=t.id,
                        title=t.title,
                        minutes=minutes_per_topic,
                        score=round(score, 4),
                    )
                    for score, t in slots_today
                ],
            )
        )

    return StudyPlan(
        user_id=user_id,
        exam_id=exam_id,
        exam_date=exam_day.isoformat(),
        days_to_exam=days_to_exam,
        daily_minutes=daily_minutes,
        days=plan_days,
    )
