"""M-0: cost-formula sanity tests at the BaseAgent boundary."""

from __future__ import annotations

from api.agent.base import BaseAgent


def test_cache_hit_drives_cost_down(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message(input_tokens=10_000, output_tokens=0))
    fake_anthropic.messages.queue(
        fake_message(input_tokens=0, cache_read_input_tokens=10_000, output_tokens=0)
    )

    agent = BaseAgent(
        name="x",
        system_prompt="...",
        client=fake_anthropic,
        model="claude-opus-4-7",
    )

    cold = agent.run("first").usage.cost_usd
    warm = agent.run("second").usage.cost_usd

    # Cache reads are billed at 10% of input rate, so warm must be ~10% of cold.
    assert warm < cold
    assert warm == round(cold * 0.10, 6)


def test_no_cache_when_disabled(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message())
    agent = BaseAgent(
        name="x",
        system_prompt="plain",
        client=fake_anthropic,
        cache_system=False,
    )
    agent.run("?")

    sent_system = fake_anthropic.messages.calls[0]["system"]
    # When caching is off the wrapper passes the plain string.
    assert sent_system == "plain"
