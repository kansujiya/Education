"""Optional Langfuse tracing.

If Langfuse keys are not configured, all calls become no-ops so the agent
runtime works on a fresh laptop without any external accounts.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from shared.tracing import AgentRunResult

from api.config import settings

logger = logging.getLogger(__name__)


def _langfuse_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


@contextmanager
def trace_agent_run(agent_name: str, model: str, user_message: str) -> Any:
    """Yield a tracer object you can call ``record(result)`` on.

    No-op when Langfuse isn't configured.
    """
    if not _langfuse_enabled():
        yield _NoopTracer()
        return

    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("langfuse not installed; tracing disabled")
        yield _NoopTracer()
        return

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host or None,
    )
    trace = client.trace(name=f"agent:{agent_name}", input={"user": user_message})
    try:
        yield _LangfuseTracer(trace=trace, agent_name=agent_name, model=model)
    finally:
        client.flush()


class _NoopTracer:
    def record(self, _result: AgentRunResult) -> None:
        return None


class _LangfuseTracer:
    def __init__(self, trace: Any, agent_name: str, model: str) -> None:
        self._trace = trace
        self._agent_name = agent_name
        self._model = model

    def record(self, result: AgentRunResult) -> None:
        try:
            self._trace.update(
                output={"text": result.text},
                metadata={
                    "model": self._model,
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "cache_read_input_tokens": result.usage.cache_read_input_tokens,
                    "cache_hit_ratio": result.usage.cache_hit_ratio,
                    "cost_usd": result.usage.cost_usd,
                    "duration_ms": result.duration_ms,
                },
            )
        except Exception:
            logger.exception("langfuse trace update failed")
