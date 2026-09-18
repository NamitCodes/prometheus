"""`research search ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from prometheus.cli._async import run
from prometheus.services.retrieval import search_knowledge

app = typer.Typer(help="Search project knowledge.")
console = Console()


@app.command("knowledge")
def knowledge(
    project_id: str = typer.Argument(..., help="Project ID to search within"),
    query: str = typer.Argument(..., help="Search query"),
    document_id: str | None = typer.Option(None, "--document", "-d", help="Restrict to one document"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search a project's ingested documents."""
    results = run(search_knowledge(query, project_id=project_id, document_id=document_id, limit=limit))

    if not results:
        console.print("No results.")
        return

    table = Table(title=f"Knowledge search: {query!r}")
    table.add_column("Score", justify="right")
    table.add_column("Document ID", overflow="fold")
    table.add_column("Page")
    table.add_column("Text")
    for r in results:
        location = str(r.page_number) if r.page_number is not None else (
            f"slide {r.slide_number}" if r.slide_number is not None else "-"
        )
        table.add_row(f"{r.score:.3f}", r.document_id or "-", location, r.text[:120])
    console.print(table)
