"""`research crawl ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console

from prometheus.cli._async import ensure_db_ready, run
from prometheus.services.projects import get_project

app = typer.Typer(help="Crawl and index web pages into a project.")
console = Console()


@app.command("url")
def url_command(
    project_id: str = typer.Argument(..., help="Project ID to index pages into"),
    start_url: str = typer.Argument(..., help="URL to start crawling from"),
    max_pages: int = typer.Option(10, "--max-pages", help="Maximum pages to crawl"),
    max_depth: int = typer.Option(2, "--max-depth", help="Maximum link depth from the start URL"),
) -> None:
    """Crawl a site starting at a URL and index the pages into a project."""
    ensure_db_ready()
    if run(get_project(project_id)) is None:
        console.print(f"[red]No such project[/red] {project_id}")
        raise typer.Exit(code=1)

    from prometheus.tasks.web_tasks import crawl_and_index

    crawl_and_index.delay(project_id, start_url, max_pages=max_pages, max_depth=max_depth)
    console.print(
        f"[green]Queued crawl[/green] of {start_url} (max {max_pages} pages, depth {max_depth}) "
        f"into project {project_id}"
    )
