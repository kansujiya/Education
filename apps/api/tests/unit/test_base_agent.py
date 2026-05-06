"""M-0 unit tests for BaseAgent.

These tests do not call Anthropic; they use a fake client whose responses
are scripted in fixtures (see conftest.py).
"""

from __future__ import annotations

from api.agent.base import BaseAgent


def test_echo_agent_returns_text(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message(text="42"))

    agent = BaseAgent(
        name="echo",
        system_prompt="You are an echo.",
        client=fake_anthropic,
        model="claude-opus-4-7",
    )

    result = agent.run("what's the answer?")

    assert result.text == "42"
    assert result.usage.model == "claude-opus-4-7"
    assert len(fake_anthropic.messages.calls) == 1


def test_system_prompt_is_cache_controlled(fake_anthropic, fake_message) -> None:
    """Caching is on by default; the system block must carry cache_control."""
    fake_anthropic.messages.queue(fake_message())

    agent = BaseAgent(
        name="echo",
        system_prompt="cached prompt",
        client=fake_anthropic,
    )
    agent.run("hello")

    sent_system = fake_anthropic.messages.calls[0]["system"]
    assert isinstance(sent_system, list)
    assert sent_system[0]["text"] == "cached prompt"
    assert sent_system[0]["cache_control"] == {"type": "ephemeral"}


def test_prompt_cache_hit_on_second_call(fake_anthropic, fake_message) -> None:
    """First call: cache miss (creation tokens). Second: cache hit (read tokens)."""
    fake_anthropic.messages.queue(fake_message(input_tokens=10, cache_creation_input_tokens=500))
    fake_anthropic.messages.queue(fake_message(input_tokens=10, cache_read_input_tokens=500))

    agent = BaseAgent(
        name="echo",
        system_prompt="big system prompt",
        client=fake_anthropic,
    )

    first = agent.run("question 1")
    second = agent.run("question 2")

    assert first.usage.cache_read_input_tokens == 0
    assert first.usage.cache_creation_input_tokens == 500
    assert first.usage.cache_hit_ratio == 0.0

    assert second.usage.cache_read_input_tokens == 500
    assert second.usage.cache_hit_ratio > 0.95


def test_cost_usd_recorded(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message(input_tokens=1000, output_tokens=1000))
    agent = BaseAgent(
        name="echo",
        system_prompt="...",
        client=fake_anthropic,
        model="claude-opus-4-7",
    )

    result = agent.run("hi")
    # 1000 * $15/M + 1000 * $75/M = $0.09
    assert result.usage.cost_usd == 0.09


def test_streaming_yields_chunks(fake_anthropic) -> None:
    fake_anthropic.messages.queue_stream(["hel", "lo ", "world"])
    agent = BaseAgent(
        name="streamer",
        system_prompt="...",
        client=fake_anthropic,
    )

    chunks = list(agent.stream("hi"))

    assert chunks == ["hel", "lo ", "world"]
    assert len(fake_anthropic.messages.stream_calls) == 1


def test_default_model_used_when_unspecified(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message())
    agent = BaseAgent(name="x", system_prompt="...", client=fake_anthropic)
    agent.run("?")
    assert fake_anthropic.messages.calls[0]["model"] == agent.model
    assert agent.model.startswith("claude-")
