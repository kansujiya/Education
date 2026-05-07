"""M-3 demo lock-in: Tutor↔Examiner evaluator-optimiser loop.

We use the eval fake (deterministic judgement keyed off the learner's
answer text) so the loop's behaviour is fully controlled.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from api.agents import ExaminerAgent, TutorAgent, TutorExaminerLoop
from api.bus.events import EVENTS_STREAM
from api.rag import NotesIndex
from fakeredis import aioredis as fake_aioredis

REPO = Path(__file__).resolve().parents[4]
NOTES = REPO / "seeds" / "notes_aws_ccp.jsonl"


@pytest.fixture
def fake_redis():
    return fake_aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def loop(fake_anthropic_eval) -> TutorExaminerLoop:
    notes = NotesIndex.from_jsonl(NOTES)
    tutor = TutorAgent(client=fake_anthropic_eval, notes=notes)
    examiner = ExaminerAgent(client=fake_anthropic_eval)
    return TutorExaminerLoop(tutor=tutor, examiner=examiner)


def _good_answer(question, _idx, _iter) -> str:
    """Hits one of the rubric's seeded key points → judged correct."""
    return f"My answer mentions {question.key_points[0]} clearly."


def _bad_answer(_question, _idx, _iter) -> str:
    """No key-point mention → judged incorrect."""
    return "completely off-topic word salad"


@pytest.mark.asyncio
async def test_pass_on_first_iteration(fake_redis, loop) -> None:
    result = await loop.run(
        topic_id="cloud-concepts",
        topic_title="Cloud Concepts",
        user_id="u_a",
        get_answer=_good_answer,
        redis=fake_redis,
    )
    assert result.passed is True
    assert result.iterations == 1
    assert result.final_score >= 0.7
    # topic.taught + topic.understood on the stream.
    entries = await fake_redis.xread({EVENTS_STREAM: 0})
    payloads = [pair[1]["data"] for pair in entries[0][1]]
    assert any("topic.taught" in p for p in payloads)
    assert any("topic.understood" in p for p in payloads)


@pytest.mark.asyncio
async def test_loop_caps_at_three(fake_redis, loop) -> None:
    result = await loop.run(
        topic_id="cloud-concepts",
        topic_title="Cloud Concepts",
        user_id="u_a",
        get_answer=_bad_answer,
        redis=fake_redis,
    )
    assert result.passed is False
    assert result.iterations == 3, "loop must cap at 3 iterations"
    assert len(result.log) == 3


@pytest.mark.asyncio
async def test_misunderstood_emitted_after_max_iterations(fake_redis, loop) -> None:
    await loop.run(
        topic_id="cloud-concepts",
        topic_title="Cloud Concepts",
        user_id="u_a",
        get_answer=_bad_answer,
        redis=fake_redis,
    )
    entries = await fake_redis.xread({EVENTS_STREAM: 0})
    payloads = [pair[1]["data"] for pair in entries[0][1]]
    assert any("topic.misunderstood" in p for p in payloads)
    assert not any("topic.understood" in p for p in payloads)


@pytest.mark.asyncio
async def test_re_teach_uses_previous_gap(fake_redis, loop, fake_anthropic_eval) -> None:
    """On the second iteration, the Tutor's prompt must carry the gap."""
    iter([_bad_answer, _bad_answer, _good_answer])

    def varying_answer(question, idx, it):
        # First two iterations bad, third correct → loop ends iter 3 PASS.
        return _good_answer(question, idx, it) if it == 2 else _bad_answer(question, idx, it)

    result = await loop.run(
        topic_id="cloud-concepts",
        topic_title="Cloud Concepts",
        user_id="u_b",
        get_answer=varying_answer,
        redis=fake_redis,
    )
    assert result.passed is True
    assert result.iterations == 3

    # The Tutor's iteration-2 / iteration-3 stream calls must include
    # the previous-gap header.
    streams = fake_anthropic_eval.messages.stream_calls
    assert len(streams) >= 2
    second_user_msg = streams[1]["messages"][0]["content"]
    assert "Previous learner gap" in second_user_msg


@pytest.mark.asyncio
async def test_event_carries_score(fake_redis, loop) -> None:
    result = await loop.run(
        topic_id="cloud-concepts",
        topic_title="Cloud Concepts",
        user_id="u_c",
        get_answer=_good_answer,
        redis=fake_redis,
    )
    assert result.passed
    entries = await fake_redis.xread({EVENTS_STREAM: 0})
    payloads = [pair[1]["data"] for pair in entries[0][1]]
    understood = next(p for p in payloads if "topic.understood" in p)
    # Score is in the JSON envelope.
    assert "1.0" in understood or "0.9" in understood or "0.8" in understood
    _ = result  # explicit
