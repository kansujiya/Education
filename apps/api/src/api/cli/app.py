"""``edu`` CLI — demo surface for each milestone.

M-0:
    edu ask "Explain mutex in one paragraph"
M-1:
    edu load-exam aws-ccp
    edu show-syllabus aws-ccp [--user u_demo]
M-2:
    edu set-language --user u_demo --lang hi
    edu teach --topic cloud-concepts.benefits [--user u_demo] [--lang hi]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.tree import Tree
from shared.models import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    Language,
    SyllabusTopic,
)

from api.agent.base import BaseAgent
from api.agents import TutorAgent
from api.config import settings
from api.db.repositories import SyllabusRepo, UserRepo
from api.db.session import db_session
from api.loaders.syllabus import load_exam_via_mcp
from api.mcp import MCPClient, MCPServerSpec
from api.rag import NotesIndex


def _validate_language(value: str | None) -> Language | None:
    if value is None:
        return None
    for supported in SUPPORTED_LANGUAGES:
        if value == supported:
            return supported
    raise typer.BadParameter(
        f"unsupported language {value!r}. Choose from: {', '.join(SUPPORTED_LANGUAGES)}"
    )


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_NOTES_PATH = REPO_ROOT / "seeds" / "notes_aws_ccp.jsonl"

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
    lang: str = typer.Option(
        "en",
        "--lang",
        "-l",
        help=f"Output language. One of: {', '.join(SUPPORTED_LANGUAGES)}.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream the response token-by-token.",
    ),
) -> None:
    """Ask a question to a single helpful-assistant agent."""
    language = _validate_language(lang) or "en"
    client = _build_anthropic_client()
    agent = BaseAgent(
        name="assistant",
        system_prompt=(
            "You are a concise, friendly tutor. Answer in plain language. "
            "Use analogies where they help. Cite sources only if you are sure. "
            f"Reply in {LANGUAGE_NAMES[language]}."
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


# ---- M-2 commands ----------------------------------------------------


@app.command(name="set-language")
def set_language(
    user: str = typer.Option(..., "--user", "-u"),
    lang: str = typer.Option(
        ...,
        "--lang",
        "-l",
        help=f"Language code. One of: {', '.join(SUPPORTED_LANGUAGES)}.",
    ),
) -> None:
    """Persist the user's preferred language for all future agent runs."""
    language = _validate_language(lang)
    assert language is not None  # _validate_language raises if missing

    async def _run() -> None:
        async with db_session() as db:
            await UserRepo(db).upsert(user, email=f"{user}@example.com")
            await UserRepo(db).set_language(user, language)
        console.print(
            f"[green]✔[/green] Language for [bold]{user}[/bold] set to "
            f"[bold]{LANGUAGE_NAMES[language]}[/bold] ({language})."
        )

    asyncio.run(_run())


@app.command(name="teach")
def teach(
    topic: str = typer.Option(..., "--topic", "-t", help="Topic id, e.g. cloud-concepts.benefits"),
    user: str = typer.Option("u_demo", "--user", "-u"),
    level: str = typer.Option("novice", "--level", help="novice|intermediate|advanced"),
    lang: str = typer.Option(
        None,
        "--lang",
        "-l",
        help="Override the user's saved language. en|hi.",
    ),
    out_dir: str = typer.Option(
        "out", "--out", help="Directory to write lesson.md and mindmap.{mmd,svg}."
    ),
    notes_path: str = typer.Option(
        str(DEFAULT_NOTES_PATH),
        "--notes",
        help="JSONL file of seeded notes for RAG.",
    ),
) -> None:
    """Stream a lesson on TOPIC, then render and write the mind map."""
    override = _validate_language(lang)

    async def _run() -> None:
        async with db_session() as db:
            user_row = await UserRepo(db).upsert(user, email=f"{user}@example.com")
            tree = await SyllabusRepo(db).fetch_tree("aws-ccp")
        language: Language = override or user_row.language  # type: ignore[assignment]
        topic_title = (
            _find_topic_title(tree, topic) or topic.split(".")[-1].replace("-", " ").title()
        )

        client = _build_anthropic_client()
        notes = NotesIndex.from_jsonl(notes_path)
        tutor = TutorAgent(client=client, notes=notes)

        console.print(f"[bold]Topic:[/bold] {topic_title}")
        console.print(f"[bold]Language:[/bold] {LANGUAGE_NAMES[language]} ({language})\n")
        console.print("[dim]Sources used:[/dim]")
        chunks_iter, retrieved = tutor.stream_lesson(
            topic, topic_title, level=level, language=language
        )
        for r in retrieved:
            console.print(f"  [dim]- {r.chunk.source}[/dim]")
        console.print()

        parts: list[str] = []
        for chunk in chunks_iter:
            sys.stdout.write(chunk)
            sys.stdout.flush()
            parts.append(chunk)
        sys.stdout.write("\n")
        lesson_md = "".join(parts)

        nodes = tutor.extract_mindmap(topic_title, lesson_md, language=language)
        mindmap = await _render_mindmap_via_mcp(nodes)

        out = Path(out_dir) / topic
        out.mkdir(parents=True, exist_ok=True)
        (out / "lesson.md").write_text(lesson_md)
        (out / "mindmap.mmd").write_text(mindmap["mermaid"])
        (out / "mindmap.svg").write_text(mindmap["svg"])

        console.print()
        console.print(f"[green]✔[/green] Saved to {out}/")
        console.print(f"  - {out}/lesson.md")
        console.print(f"  - {out}/mindmap.svg  (open in any browser)")
        console.print(f"  - {out}/mindmap.mmd")

    asyncio.run(_run())


def _find_topic_title(tree: list[SyllabusTopic], topic_id: str) -> str | None:
    for t in tree:
        if t.id == topic_id:
            return t.title
        if t.children:
            found = _find_topic_title(t.children, topic_id)
            if found:
                return found
    return None


async def _render_mindmap_via_mcp(node: dict[str, object]) -> dict[str, str]:
    spec = MCPServerSpec(
        command="python",
        args=["-m", "mcp_mindmap.server"],
        env=os.environ.copy(),
    )
    result = await MCPClient(spec).call("render_mindmap", {"node": node})
    if not isinstance(result, dict):
        raise RuntimeError(f"mcp-mindmap returned unexpected payload: {result!r}")
    return result


if __name__ == "__main__":
    app()
