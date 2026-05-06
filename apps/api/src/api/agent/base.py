"""BaseAgent: the unit every Education AI agent extends.

One agent = one system prompt + one model + (later) a list of tools. All
agents share this runtime so prompt caching, usage accounting, and tracing
are wired exactly once.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from shared.tracing import AgentRunResult

from api.agent.anthropic_client import AnthropicWrapper, CompletionRequest
from api.agent.tracing import trace_agent_run
from api.config import settings


class BaseAgent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        client: Any,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        cache_system: bool = True,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.model = model or settings.default_model
        self.max_tokens = max_tokens
        self.cache_system = cache_system
        self._wrapper = AnthropicWrapper(client)

    def run(self, user_message: str) -> AgentRunResult:
        req = CompletionRequest(
            model=self.model,
            system_prompt=self.system_prompt,
            user_message=user_message,
            max_tokens=self.max_tokens,
            cache_system=self.cache_system,
        )
        with trace_agent_run(self.name, self.model, user_message) as tracer:
            result = self._wrapper.complete(req)
            tracer.record(result)
            return result

    def stream(self, user_message: str) -> Iterator[str]:
        req = CompletionRequest(
            model=self.model,
            system_prompt=self.system_prompt,
            user_message=user_message,
            max_tokens=self.max_tokens,
            cache_system=self.cache_system,
        )
        yield from self._wrapper.stream(req)
