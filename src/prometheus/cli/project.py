"""`research project ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from prometheus.cli._async import ensure_db_ready, run
from prometheus.services import projects as projects_service

app = typer.Typer(help="Manage research projects (workspaces).")
console = Console()


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", "--description", "-d", help="Optional description"),
) -> None:
    """Create a new project."""
    ensure_db_ready()
    project = run(projects_service.create_project(name=name, description=description))
    console.print(f"[green]Created project[/green] {project.id} — {project.name}")


@app.command("list")
def list_() -> None:
    """List all projects."""
    ensure_db_ready()
    project_rows = run(projects_service.list_projects())

    if not project_rows:
        console.print("No projects yet. Create one with: research project create <name>")
        return

    table = Table(title="Projects")
    table.add_column("ID", overflow="fold")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Created")
    for project in project_rows:
        table.add_row(project.id, project.name, project.description, str(project.created_at))
    console.print(table)


@app.command("delete")
def delete(project_id: str = typer.Argument(..., help="Project ID")) -> None:
    """Delete a project and its documents."""
    ensure_db_ready()
    deleted = run(projects_service.delete_project(project_id))
    if deleted:
        console.print(f"[green]Deleted project[/green] {project_id}")
    else:
        console.print(f"[red]No such project[/red] {project_id}")
        raise typer.Exit(code=1)
