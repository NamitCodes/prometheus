"""Root `research` CLI (Typer app). See pyproject.toml [project.scripts]."""
from __future__ import annotations

import typer

from prometheus.cli import chat, crawl, document, project, search
from prometheus.cli import eval as eval_cli

app = typer.Typer(
    name="research",
    help="Prometheus: an AI research workspace. CLI-first (new-plan.md).",
    no_args_is_help=True,
)

app.add_typer(project.app, name="project")
app.add_typer(document.app, name="document")
app.add_typer(search.app, name="search")
app.add_typer(chat.app, name="chat")
app.add_typer(crawl.app, name="crawl")
app.add_typer(eval_cli.app, name="eval")


if __name__ == "__main__":
    app()
