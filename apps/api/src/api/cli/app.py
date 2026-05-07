"""``edu`` CLI — demo surface for each milestone.

M-0:
    edu ask "Explain mutex in one paragraph"
M-1:
    edu load-exam aws-ccp
    edu show-syllabus aws-ccp [--user u_demo]
M-2:
    edu set-language --user u_demo --lang hi
    edu teach --topic cloud-concepts.benefits [--user u_demo] [--lang hi]
M-3:
    edu teach --topic cloud-concepts --interactive
M-4:
    edu cards --user u_demo --topic cloud-concepts.benefits
    edu attempt --user u_demo --card <card_id> --answer "..."
    edu progress --user u_demo
M-5:
    edu onboard --user u_demo --exam aws-ccp --exam-date 2026-08-01 --daily-minutes 60
    edu plan --user u_demo
    edu simulate-fall-behind --user u_demo
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.tree import Tree
from shared.events import CardAttempted, PlanReplan
from shared.models import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    Language,
    SyllabusTopic,
)
from shared.tools import Judgement, Question

from api.agent.base import BaseAgent
from api.agents import (
    AssessorAgent,
    CardSpec,
    CoachAgent,
    ExaminerAgent,
    OnboardingAgent,
    TutorAgent,
    TutorExaminerLoop,
)
from api.bus.events import emit_event, get_redis
from api.config import settings
from api.db import models as orm
from api.db.repositories import (
    CardAttemptRepo,
    CardRepo,
    PlanRepo,
    ProgressRepo,
    SyllabusRepo,
    UserRepo,
)
from api.db.session import db_session
from api.listeners import dispatch_event, set_pyq_frequency_provider
from api.loaders.syllabus import load_exam_via_mcp
from api.mcp import MCPClient, MCPServerSpec
from api.planning import StudyPlan
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
    interactive: bool = typer.Option(
        False,
        "--interactive/--no-interactive",
        help="Run the Tutor↔Examiner Socratic loop after the lesson.",
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
    if interactive:
        return _run_interactive_teach(topic=topic, user=user, level=level, override=override)

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


def _run_interactive_teach(
    *,
    topic: str,
    user: str,
    level: str,
    override: Language | None,
) -> None:
    """Run the Tutor↔Examiner Socratic loop end-to-end on the CLI.

    On pass: prints "Understood ✓"; emits topic.understood.
    On fail (max-iters): prints "Needs revision"; emits topic.misunderstood.
    """
    notes_path = DEFAULT_NOTES_PATH

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
        loop = TutorExaminerLoop(
            tutor=TutorAgent(client=client, notes=notes),
            examiner=ExaminerAgent(client=client),
        )

        console.print(f"[bold]Topic:[/bold] {topic_title}")
        console.print(f"[bold]Language:[/bold] {LANGUAGE_NAMES[language]} ({language})\n")

        def stream_chunk(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()

        def show_question(q: Question, idx: int, it: int) -> None:
            console.print()
            console.print(f"[bold]Iteration {it + 1}, Q{idx + 1}:[/bold] {q.text}")

        def get_answer(_q: Question, _idx: int, _it: int) -> str:
            answer: str = typer.prompt("Your answer", default="")
            return answer.strip()

        def show_judgement(_q: Question, _answer: str, judgement: Judgement) -> None:
            mark = "[green]✓[/green]" if judgement.correct else "[yellow]✗[/yellow]"
            console.print(f"  {mark} score={judgement.score:.2f}  {judgement.gap}")

        result = await loop.run(
            topic_id=topic,
            topic_title=topic_title,
            user_id=user,
            get_answer=get_answer,
            language=language,
            level=level,
            on_lesson_chunk=stream_chunk,
            on_question=show_question,
            on_judgement=show_judgement,
        )

        sys.stdout.write("\n")
        if result.passed:
            console.print(
                f"[bold green]Understood ✓[/bold green] "
                f"(iter {result.iterations}/{loop.max_iterations}, "
                f"score {result.final_score:.2f})"
            )
        else:
            console.print(
                f"[bold yellow]Needs revision[/bold yellow] "
                f"(iter {result.iterations}/{loop.max_iterations}, "
                f"score {result.final_score:.2f}). "
                f"Last gap: {result.last_gap or 'n/a'}"
            )

    asyncio.run(_run())


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


# ---- M-4 commands ----------------------------------------------------


@app.command(name="cards")
def cards(
    topic: str = typer.Option(..., "--topic", "-t"),
    user: str = typer.Option("u_demo", "--user", "-u"),
    n: int = typer.Option(6, "--count", "-n"),
    lang: str = typer.Option(None, "--lang", "-l"),
) -> None:
    """Issue ``n`` PYQ-grounded cards for TOPIC and persist them."""
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
        notes = NotesIndex.from_jsonl(DEFAULT_NOTES_PATH)
        tutor = TutorAgent(client=client, notes=notes)
        # We need a recent lesson to feed the Assessor. Use the cached path.
        lesson_md, _ = _stream_lesson_collected(tutor, topic, topic_title, language)
        pyqs = await _fetch_pyqs(topic, k=8)
        assessor = AssessorAgent(client=client)
        specs: list[CardSpec] = assessor.issue_cards(
            topic_title, lesson_md, pyqs, n=n, language=language
        )

        async with db_session() as db:
            await UserRepo(db).upsert(user, email=f"{user}@example.com")
            cards_repo = CardRepo(db, user)
            persisted = await cards_repo.add_many(
                [
                    {
                        "topic_id": topic,
                        "type": s.type,
                        "prompt": s.prompt,
                        "answer": s.answer,
                        "key_points": list(s.key_points),
                        "source_pyq_id": s.source_pyq_id,
                    }
                    for s in specs
                ]
            )
            await db.commit()

        console.print(f"[green]Issued {len(persisted)} cards[/green] for {topic_title}\n")
        for c, spec in zip(persisted, specs, strict=True):
            console.print(f"[bold]{c.id}[/bold]  [dim]{c.type}[/dim]  {spec.prompt}")
            if spec.source_pyq_id:
                console.print(f"  [dim]source: {spec.source_pyq_id} ({spec.source_year})[/dim]")

    asyncio.run(_run())


@app.command(name="attempt")
def attempt(
    card_id: str = typer.Option(..., "--card", "-c"),
    answer: str = typer.Option(..., "--answer", "-a"),
    user: str = typer.Option("u_demo", "--user", "-u"),
    lang: str = typer.Option(None, "--lang", "-l"),
) -> None:
    """Submit an answer for CARD_ID; judges, persists, fires listeners."""
    override = _validate_language(lang)

    async def _run() -> None:
        async with db_session() as db:
            user_row = await UserRepo(db).upsert(user, email=f"{user}@example.com")
            card = await CardRepo(db, user).get(card_id)
            if card is None:
                console.print(f"[red]No card {card_id!r} for user {user!r}.[/red]")
                raise typer.Exit(code=1)
            await db.commit()

        language: Language = override or user_row.language  # type: ignore[assignment]
        client = _build_anthropic_client()
        assessor = AssessorAgent(client=client)
        spec = CardSpec.model_validate(
            {
                "type": card.type,
                "prompt": card.prompt,
                "answer": card.answer,
                "key_points": list(card.key_points or []),
                "source_pyq_id": card.source_pyq_id,
                "source_year": None,
            }
        )
        judgement = assessor.grade_attempt(spec, answer, language=language)

        redis = get_redis()
        async with db_session() as db:
            attempt_row = await CardAttemptRepo(db, user).add(
                card_id=card_id, score=judgement.score
            )
            await db.commit()
            event = CardAttempted(
                user_id=user,
                card_id=card_id,
                topic_id=card.topic_id,
                score=judgement.score,
                correct=judgement.correct,
            )
            await emit_event(event, redis=redis, db=db)
            await db.commit()
            await dispatch_event(event, db=db, redis=redis)
            await db.commit()

        mark = "[green]✓[/green]" if judgement.correct else "[yellow]✗[/yellow]"
        console.print(
            f"{mark} score={judgement.score:.2f}  due_at={attempt_row.due_at}  {judgement.gap}"
        )

    asyncio.run(_run())


@app.command(name="progress")
def progress(
    user: str = typer.Option("u_demo", "--user", "-u"),
) -> None:
    """Print mastery + last-touched per topic for the user."""

    async def _run() -> None:
        async with db_session() as db:
            await UserRepo(db).upsert(user, email=f"{user}@example.com")
            rows = await ProgressRepo(db, user).list_all()
        if not rows:
            console.print("[dim]No progress yet — issue some cards and attempt them.[/dim]")
            return
        rows.sort(key=lambda r: r.mastery, reverse=True)
        for r in rows:
            bar_len = round(r.mastery * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            console.print(f"  {bar}  {r.mastery * 100:5.1f}%  [bold]{r.topic_id}[/bold]")

    asyncio.run(_run())


def _stream_lesson_collected(
    tutor: TutorAgent,
    topic: str,
    topic_title: str,
    language: Language,
) -> tuple[str, object]:
    """Run the Tutor and collect the full lesson text without printing.

    Used by ``edu cards`` so the Assessor has lesson context. We don't
    care about provenance here — the demo prints sources elsewhere.
    """
    chunks_iter, retrieved = tutor.stream_lesson(topic, topic_title, language=language)
    return "".join(chunks_iter), retrieved


async def _fetch_pyqs(topic_id: str, *, k: int = 8) -> list[dict[str, object]]:
    """Call mcp-pyq.search_pyq and return the dict results."""
    spec = MCPServerSpec(
        command="python",
        args=["-m", "mcp_pyq.server"],
        env=os.environ.copy(),
    )
    out = await MCPClient(spec).call(
        "search_pyq", {"query": topic_id, "k": k, "topic_id": topic_id}
    )
    if not isinstance(out, dict):
        return []
    results = out.get("results")
    if not isinstance(results, list):
        return []
    # Each result already includes id, year, stem, model_answer, key_points.
    return list(results)


# Keep ``orm`` referenced so static checkers don't trim the import.
_ORM_KEEP: type[orm.Card] = orm.Card


# ---- M-5 commands ----------------------------------------------------


def _parse_exam_date(value: str) -> datetime:
    """Accept ``YYYY-MM-DD`` or any ISO timestamp; force timezone-aware."""
    text = value.strip()
    if "T" not in text and len(text) == 10:
        text = f"{text}T00:00:00+00:00"
    elif text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


@app.command(name="onboard")
def onboard(
    user: str = typer.Option("u_demo", "--user", "-u"),
    exam: str = typer.Option(..., "--exam", "-e"),
    exam_date: str = typer.Option(..., "--exam-date", help="YYYY-MM-DD or ISO timestamp."),
    daily_minutes: int = typer.Option(60, "--daily-minutes"),
    level: str = typer.Option("novice", "--level"),
    lang: str = typer.Option(None, "--lang", "-l"),
) -> None:
    """Persist a profile and emit ``user.onboarded``."""
    if level not in ("novice", "intermediate", "advanced"):
        raise typer.BadParameter("level must be novice|intermediate|advanced")

    parsed_date = _parse_exam_date(exam_date)
    language = _validate_language(lang) or "en"

    async def _run() -> None:
        async with db_session() as db:
            agent = OnboardingAgent()
            result = await agent.run(
                db,
                user_id=user,
                email=f"{user}@example.com",
                exam_id=exam,
                exam_date=parsed_date,
                daily_minutes=daily_minutes,
                level=level,  # type: ignore[arg-type]
                language=language,
                redis=get_redis(),
            )
        days = (parsed_date.date() - datetime.now(UTC).date()).days
        console.print(
            f"[green]✔ Onboarded[/green] {result.user.id} · "
            f"exam=[bold]{result.profile.exam_id}[/bold] · "
            f"in {days} days · {result.profile.daily_minutes} min/day · "
            f"level={result.profile.level} · lang={result.user.language}"
        )

    asyncio.run(_run())


@app.command(name="plan")
def plan(
    user: str = typer.Option("u_demo", "--user", "-u"),
    days: int = typer.Option(7, "--days", help="Window for the printed plan."),
) -> None:
    """Print today + next-N-days plan for the user."""

    async def _run() -> None:
        pyq = await _fetch_pyq_frequency()
        async with db_session() as db:
            coach = CoachAgent()
            try:
                result = await coach.plan(db, user_id=user, pyq_frequency=pyq, days_window=days)
            except LookupError:
                console.print(
                    f"[red]No profile for {user!r}.[/red] "
                    f"Run [bold]edu onboard --user {user} --exam aws-ccp "
                    f"--exam-date YYYY-MM-DD[/bold] first."
                )
                raise typer.Exit(code=1) from None
            await db.commit()
        _print_plan(result.plan)

    asyncio.run(_run())


@app.command(name="simulate-fall-behind")
def simulate_fall_behind(
    user: str = typer.Option("u_demo", "--user", "-u"),
    bump_topic: str | None = typer.Option(
        None,
        "--bump-mastered",
        help="Mark this topic as mastered=1.0 before replanning.",
    ),
) -> None:
    """Emit ``plan.replan`` and run the listener so the demo shows
    a regenerated schedule (deprioritising mastered topics)."""

    async def _run() -> None:
        async with db_session() as db:
            await UserRepo(db).upsert(user, email=f"{user}@example.com")
            if bump_topic:
                await ProgressRepo(db, user).upsert(bump_topic, mastery=1.0)
            await db.commit()

        # Wire mcp-pyq as the frequency provider for this run.
        set_pyq_frequency_provider(_fetch_pyq_frequency)
        try:
            redis = get_redis()
            event = PlanReplan(user_id=user, reason="simulate-fall-behind")
            async with db_session() as db:
                await emit_event(event, redis=redis, db=db)
                await db.commit()
                await dispatch_event(event, db=db, redis=redis)
                await db.commit()
                latest = await PlanRepo(db, user).latest()
        finally:
            set_pyq_frequency_provider(None)

        if latest is None:
            console.print("[yellow]Replanned but no plan persisted.[/yellow]")
            raise typer.Exit(code=2)
        console.print("[green]Replanned ✓[/green]\n")
        plan_obj = StudyPlan.from_dict(dict(latest.schedule))
        _print_plan(plan_obj)

    asyncio.run(_run())


def _print_plan(plan_obj: StudyPlan) -> None:
    console.print(
        f"[bold]Plan[/bold] · exam {plan_obj.exam_id} on {plan_obj.exam_date}  "
        f"({plan_obj.days_to_exam}d to go) · {plan_obj.daily_minutes} min/day"
    )
    for d in plan_obj.days:
        if not d.topics:
            console.print(f"  [dim]{d.date}[/dim]  (rest)")
            continue
        bullets = ", ".join(f"{t.title} ({t.minutes}m)" for t in d.topics)
        console.print(f"  [bold]{d.date}[/bold]  {bullets}")


async def _fetch_pyq_frequency(window_years: int = 5) -> dict[str, int]:
    spec = MCPServerSpec(command="python", args=["-m", "mcp_pyq.server"], env=os.environ.copy())
    out = await MCPClient(spec).call("pyq_frequency", {"window_years": window_years})
    if not isinstance(out, dict):
        return {}
    counts = out.get("counts") or {}
    if not isinstance(counts, dict):
        return {}
    return {str(k): int(v) for k, v in counts.items()}


if __name__ == "__main__":
    app()
