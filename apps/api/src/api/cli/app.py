"""``edu`` CLI — the M-0 demo surface.

Usage:
    edu ask "Explain mutex in one paragraph"
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from api.agent.base import BaseAgent
from api.config import settings

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


if __name__ == "__main__":
    app()
