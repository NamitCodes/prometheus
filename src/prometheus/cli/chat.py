"""`research chat ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console

from prometheus.cli._async import ensure_db_ready, run
from prometheus.services.projects import get_project
from prometheus.workflow.graph import ChatResult, ChatSession, ask

app = typer.Typer(help="Chat with a project's knowledge base.")
console = Console()

_LLM_ERROR_HINT = (
    "[dim]If this mentions tool/function-calling support, the configured "
    "OPENROUTER_MODEL doesn't support it -- pick a tool-calling-capable "
    "model (new-plan.md section 14).[/dim]"
)


def _print_result(result: ChatResult) -> None:
    console.print(result.answer)
    if result.citations:
        console.print("\n[bold]Sources:[/bold]")
        for i, citation in enumerate(result.citations, start=1):
            if citation.get("type") == "web":
                console.print(f"  [{i}] {citation.get('title') or citation['url']} -- {citation['url']}")
                continue

            if citation.get("page_number") is not None:
                location = f"p.{citation['page_number']}"
            elif citation.get("slide_number") is not None:
                location = f"slide {citation['slide_number']}"
            else:
                location = ""
            console.print(f"  [{i}] doc={citation['document_id']} {location}")


def _require_project(project_id: str) -> None:
    ensure_db_ready()
    if run(get_project(project_id)) is None:
        console.print(f"[red]No such project[/red] {project_id}")
        raise typer.Exit(code=1)


@app.command("ask")
def ask_command(
    project_id: str = typer.Argument(..., help="Project ID"),
    question: str = typer.Argument(..., help="Question to ask"),
) -> None:
    """Ask a single question grounded in a project's ingested documents."""
    _require_project(project_id)

    try:
        result = ask(project_id, question)
    except Exception as exc:
        console.print(f"[red]LLM request failed:[/red] {exc}")
        console.print(_LLM_ERROR_HINT)
        raise typer.Exit(code=1) from exc

    _print_result(result)


@app.command("start")
def start_command(project_id: str = typer.Argument(..., help="Project ID")) -> None:
    """Start an interactive multi-turn chat session for a project."""
    _require_project(project_id)

    session = ChatSession(project_id)
    console.print(f"[bold]Research workspace:[/bold] {project_id}")
    console.print("[dim]Type your question, or 'exit'/Ctrl-D to quit.[/dim]\n")

    while True:
        try:
            question = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        try:
            result = session.ask(question)
        except Exception as exc:  # noqa: BLE001 -- REPL error boundary, continue the session
            console.print(f"[red]LLM request failed:[/red] {exc}")
            console.print(_LLM_ERROR_HINT)
            continue

        console.print("[bold green]Assistant:[/bold green]")
        _print_result(result)
        console.print()
