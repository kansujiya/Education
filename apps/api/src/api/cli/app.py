"""``edu`` CLI — demo surface for each milestone.

M-0:
    edu ask "Explain mutex in one paragraph"
M-1:
    edu load-exam aws-ccp
    edu show-syllabus aws-ccp [--user u_demo]
"""

from __future__ import annotations

import asyncio
import sys

import typer
from rich.console import Console
from rich.tree import Tree
from shared.models import SyllabusTopic

from api.agent.base import BaseAgent
from api.config import settings
from api.db.repositories import SyllabusRepo, UserRepo
from api.db.session import db_session
from api.loaders.syllabus import load_exam_via_mcp

app = typer.Typer(
    name="edu",
    help="Education AI agent runtime CLI.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _build_anthropic_client() -> object:
    """Construct the real Anthropic client. Defer import so tests don't need the package installed."""
    if not settings.anthropic_api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] Add it to .env or export it.",
        )
        raise typer.Exit(code=2)
    from anthropic import Anthropic

    return Anthropic(api_key=settings.anthropic_api_key)


@app.command()
def ask(
    question: str = typer.Argument(..., help="The question to ask."),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model override; defaults to DEFAULT_MODEL.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream the response token-by-token.",
    ),
) -> None:
    """Ask a question to a single helpful-assistant agent."""
    client = _build_anthropic_client()
    agent = BaseAgent(
        name="assistant",
        system_prompt=(
            "You are a concise, friendly tutor. Answer in plain language. "
            "Use analogies where they help. Cite sources only if you are sure."
        ),
        client=client,
        model=model or settings.default_model,
    )

    if stream:
        for chunk in agent.stream(question):
            sys.stdout.write(chunk)
            sys.stdout.flush()
        sys.stdout.write("\n")
        return

    result = agent.run(question)
    console.print(result.text)
    console.print()
    console.print(
        f"[dim]model={result.usage.model}  "
        f"in={result.usage.input_tokens}  "
        f"out={result.usage.output_tokens}  "
        f"cache_read={result.usage.cache_read_input_tokens}  "
        f"cache_hit={result.usage.cache_hit_ratio:.0%}  "
        f"cost=${result.usage.cost_usd:.4f}  "
        f"({result.duration_ms} ms)[/dim]"
    )


@app.command()
def health() -> None:
    """Print runtime config (without secrets) for sanity checks."""
    console.print(
        {
            "default_model": settings.default_model,
            "judgement_model": settings.judgement_model,
            "high_volume_model": settings.high_volume_model,
            "daily_token_budget": settings.daily_token_budget,
            "anthropic_api_key_set": bool(settings.anthropic_api_key),
            "langfuse_enabled": bool(settings.langfuse_public_key and settings.langfuse_secret_key),
        }
    )


# ---- M-1 commands ----------------------------------------------------


@app.command(name="load-exam")
def load_exam(
    exam_id: str = typer.Argument(..., help="Exam slug, e.g. aws-ccp."),
) -> None:
    """Pull the syllabus via mcp-syllabus and store it in the DB."""

    async def _run() -> None:
        async with db_session() as db:
            result = await load_exam_via_mcp(db, exam_id)
        console.print(
            f"[green]Loaded[/green] {result.name} "
            f"([dim]{result.exam_id}[/dim]): {result.topic_count} topics."
        )

    asyncio.run(_run())


@app.command(name="show-syllabus")
def show_syllabus(
    exam_id: str = typer.Argument(...),
    user: str = typer.Option(
        "u_demo",
        "--user",
        "-u",
        help="User scope. Topics are global, but this confirms the user exists.",
    ),
) -> None:
    """Print the topic tree for an exam."""

    async def _run() -> None:
        async with db_session() as db:
            await UserRepo(db).upsert(user, email=f"{user}@example.com")
            tree = await SyllabusRepo(db).fetch_tree(exam_id)
        if not tree:
            console.print(
                f"[red]No topics found for {exam_id!r}.[/red] "
                f"Run [bold]edu load-exam {exam_id}[/bold] first."
            )
            raise typer.Exit(code=1)
        rendered = Tree(f"[bold]{exam_id}[/bold]")
        for top in tree:
            _render_topic(rendered, top)
        console.print(rendered)

    asyncio.run(_run())


def _render_topic(parent: Tree, topic: SyllabusTopic) -> None:
    label = f"{topic.title} [dim](w={topic.weight:.2f})[/dim]"
    node = parent.add(label)
    for child in topic.children:
        _render_topic(node, child)


if __name__ == "__main__":
    app()
