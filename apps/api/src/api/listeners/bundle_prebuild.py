"""bundle_prebuilder: build the downloadable artefact when a topic is mastered.

Subscribed to ``topic.mastered``. The listener needs the lesson + mind
map text — the producer (CLI / API endpoint) seeds these via a caller-
provided ``BundleSourceProvider`` so the listener stays decoupled from
filesystem layout / DB lessons / mcp-mindmap subprocess.

Wire the provider with ``set_bundle_source_provider(...)``; clear it
with ``set_bundle_source_provider(None)``. Without one, the listener
silently no-ops (deterministic for tests).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis
from shared.events import Event, TopicMastered
from sqlalchemy.ext.asyncio import AsyncSession

from api.agents.export import ExportAgent
from api.listeners.dispatcher import register


@dataclass(slots=True)
class BundleSource:
    """Everything the Export needs that isn't already in the DB."""

    topic_title: str
    lesson_md: str
    mindmap_svg: str
    mindmap_mermaid: str


BundleSourceProvider = Callable[[str, str], Awaitable[BundleSource | None]]
"""(user_id, topic_id) -> BundleSource (or None to skip)."""

_provider: BundleSourceProvider | None = None
_export_agent: ExportAgent | None = None


def set_bundle_source_provider(provider: BundleSourceProvider | None) -> None:
    global _provider
    _provider = provider


def set_export_agent(agent: ExportAgent | None) -> None:
    """Inject a custom ExportAgent (tests pass one wired to a stub MCP).

    Default is ``None`` → the listener constructs a fresh
    ``ExportAgent()`` per call, which spawns ``mcp-pdf`` over stdio.
    """
    global _export_agent
    _export_agent = agent


async def bundle_prebuilder(
    event: Event,
    *,
    db: AsyncSession,
    redis: Redis,
) -> None:
    if not isinstance(event, TopicMastered):
        return
    user_id = event.user_id or ""
    if not user_id:
        return
    if _provider is None:
        return  # nothing wired; deterministic no-op

    source = await _provider(user_id, event.topic_id)
    if source is None:
        return

    agent = _export_agent or ExportAgent()
    await agent.export(
        db,
        user_id=user_id,
        topic_id=event.topic_id,
        topic_title=source.topic_title,
        lesson_md=source.lesson_md,
        mindmap_svg=source.mindmap_svg,
        mindmap_mermaid=source.mindmap_mermaid,
    )
    await db.commit()


register("topic.mastered", bundle_prebuilder)
