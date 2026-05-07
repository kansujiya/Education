"""M-3 eval lock-in: Examiner judges learner answers consistently.

The fake's judgement is deterministic: an answer is "correct" iff it
mentions one of the rubric's key points. We feed 10 hand-labelled
(answer, expected_correct) cases and assert the judge agrees with the
label at least 85% of the time.

Real-LLM precision evals can replace the fake later without changing
the test surface.
"""

from __future__ import annotations

import pytest
from api.agents import ExaminerAgent
from shared.tools import Question

# 10 cases. Key points used in the rubric: "rented capacity", "pay-as-you-go".
RUBRIC = Question(
    text="What is the cloud, in one line?",
    model_answer="Rented capacity you pay for as you go.",
    key_points=["rented capacity", "pay-as-you-go"],
)

CASES: list[tuple[str, bool]] = [
    ("It's rented capacity you pay-as-you-go.", True),
    ("Cloud means rented capacity from a provider.", True),
    ("You pay-as-you-go for what you actually use.", True),
    ("It's rented capacity, billed by the hour.", True),
    ("It is the practice of renting capacity (rented capacity).", True),
    ("It is a buzzword.", False),
    ("Magical computers somewhere.", False),
    ("It's free RAM.", False),
    ("Servers in your basement.", False),
    ("", False),
]


@pytest.mark.parametrize("answer,expected_correct", CASES)
def test_judge_agrees_with_label_on_each_case(
    fake_anthropic_eval, answer: str, expected_correct: bool
) -> None:
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    judgement = examiner.judge_answer(RUBRIC, answer)
    assert judgement.correct is expected_correct


def test_judge_precision_above_threshold(fake_anthropic_eval) -> None:
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    correct = 0
    for answer, expected in CASES:
        j = examiner.judge_answer(RUBRIC, answer)
        if j.correct == expected:
            correct += 1
    precision = correct / len(CASES)
    assert precision >= 0.85, f"judge precision too low: {precision:.2f}"


def test_gap_filled_when_incorrect(fake_anthropic_eval) -> None:
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    j = examiner.judge_answer(RUBRIC, "completely off-topic word salad")
    assert j.correct is False
    assert j.gap, "an incorrect judgement must come with a gap"


def test_gap_empty_when_correct(fake_anthropic_eval) -> None:
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    j = examiner.judge_answer(RUBRIC, "Rented capacity, pay-as-you-go.")
    assert j.correct is True
    assert j.gap == ""


def test_ask_returns_at_least_three_questions(fake_anthropic_eval) -> None:
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    questions = examiner.ask_questions(
        topic_title="Cloud Concepts",
        lesson_md="Imagine renting a kitchen by the hour …",
        n=3,
    )
    assert len(questions) >= 3
    # Each question carries grading scaffolding.
    for q in questions:
        assert q.model_answer
        assert q.key_points
