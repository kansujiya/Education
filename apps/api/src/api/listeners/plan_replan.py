"""plan_replanner: regenerate the user's plan when ``plan.replan`` fires.

PYQ frequencies are looked up via a caller-provided async provider so
the listener stays free of MCP subprocess details. Tests inject a
synthetic provider; the CLI/worker injects one that calls ``mcp-pyq``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from shared.events import Event, PlanReplan
from sqlalchemy.ext.asyncio import AsyncSession

from api.agents.coach import CoachAgent
from api.listeners.dispatcher import register

PyqFrequencyProvider = Callable[[], Awaitable[dict[str, int]]]

_provider: PyqFrequencyProvider | None = None


def set_pyq_frequency_provider(provider: PyqFrequencyProvider | None) -> None:
    """Wire how the listener obtains current PYQ frequencies.

    Called once at process startup (CLI / worker). ``None`` clears the
    binding and makes the listener a no-op (useful in tests that don't
    want this listener firing).
    """
    global _provider
    _provider = provider


def get_pyq_frequency_provider() -> PyqFrequencyProvider | None:
    return _provider


async def plan_replanner(
    event: Event,
    *,
    db: AsyncSession,
    redis: Redis,
) -> None:
    if not isinstance(event, PlanReplan):
        return
    user_id = event.user_id or ""
    if not user_id:
        return
    if _provider is None:
        return  # nothing to do without an injected source

    pyq_frequency = await _provider()
    coach = CoachAgent()
    await coach.plan(db, user_id=user_id, pyq_frequency=pyq_frequency)
    await db.commit()


register("plan.replan", plan_replanner)
