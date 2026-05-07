"""M-2 unit tests for tool-use plumbing in BaseAgent."""

from __future__ import annotations

from api.agent.anthropic_client import ToolDefinition
from api.agent.base import BaseAgent


def test_tool_use_returned_as_dict(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(
        fake_message(
            text="",
            tool_use={"name": "submit_lesson", "input": {"summary": "ok"}},
        )
    )
    agent = BaseAgent(
        name="t",
        system_prompt="...",
        client=fake_anthropic,
        tools=[
            ToolDefinition(
                name="submit_lesson",
                description="submit",
                input_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
            )
        ],
    )

    result = agent.run("teach me", force_tool="submit_lesson")

    assert result.tool_use is not None
    assert result.tool_use["name"] == "submit_lesson"
    assert result.tool_use["input"] == {"summary": "ok"}


def test_force_tool_sends_tool_choice(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message(text="", tool_use={"name": "x", "input": {}}))
    agent = BaseAgent(
        name="t",
        system_prompt="...",
        client=fake_anthropic,
        tools=[ToolDefinition(name="x", description="x", input_schema={"type": "object"})],
    )
    agent.run("hi", force_tool="x")

    sent = fake_anthropic.messages.calls[0]
    assert sent["tool_choice"] == {"type": "tool", "name": "x"}
    assert sent["tools"] == [{"name": "x", "description": "x", "input_schema": {"type": "object"}}]


def test_no_tools_no_tool_choice_in_payload(fake_anthropic, fake_message) -> None:
    fake_anthropic.messages.queue(fake_message())
    agent = BaseAgent(name="t", system_prompt="...", client=fake_anthropic)
    agent.run("hi")

    sent = fake_anthropic.messages.calls[0]
    assert "tools" not in sent
    assert "tool_choice" not in sent
