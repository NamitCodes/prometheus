"""`research document ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from prometheus.cli._async import ensure_db_ready, run
from prometheus.services import documents as documents_service
from prometheus.services.documents import DocumentValidationError

app = typer.Typer(help="Manage documents within a project.")
console = Console()


@app.command("add")
def add(
    project_id: str = typer.Argument(..., help="Project ID to add the document to"),
    file_path: str = typer.Argument(..., help="Path to a .pdf, .docx, .pptx, or .txt file"),
) -> None:
    """Upload a document into a project and queue it for processing."""
    ensure_db_ready()
    try:
        document = run(
            documents_service.add_and_process_document(project_id=project_id, file_path=file_path)
        )
    except DocumentValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Added document[/green] {document.id} — {document.filename} "
        f"(queued for processing; run `research document show {document.id}` to check status)"
    )


@app.command("reindex")
def reindex(document_id: str = typer.Argument(..., help="Document ID")) -> None:
    """Re-run the processing pipeline for an already-uploaded document."""
    ensure_db_ready()
    try:
        run(documents_service.reprocess_document(document_id))
    except DocumentValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Queued for reprocessing[/green] {document_id}")


@app.command("list")
def list_(
    project_id: str | None = typer.Option(None, "--project", "-p", help="Filter by project ID"),
) -> None:
    """List documents (optionally scoped to a project)."""
    ensure_db_ready()
    document_rows = run(documents_service.list_documents(project_id=project_id))

    if not document_rows:
        console.print("No documents yet.")
        return

    table = Table(title="Documents")
    table.add_column("ID", overflow="fold")
    table.add_column("Project ID", overflow="fold")
    table.add_column("Filename")
    table.add_column("Status")
    table.add_column("Created")
    for document in document_rows:
        table.add_row(
            document.id, document.project_id, document.filename, document.status, str(document.created_at)
        )
    console.print(table)


@app.command("show")
def show(document_id: str = typer.Argument(..., help="Document ID")) -> None:
    """Show details for a single document."""
    ensure_db_ready()
    document = run(documents_service.get_document(document_id))
    if document is None:
        console.print(f"[red]No such document[/red] {document_id}")
        raise typer.Exit(code=1)

    console.print(f"ID:          {document.id}")
    console.print(f"Project ID:  {document.project_id}")
    console.print(f"Filename:    {document.filename}")
    console.print(f"Status:      {document.status}")
    console.print(f"Storage key: {document.storage_path}")
    console.print(f"Created:     {document.created_at}")
    if document.error:
        console.print(f"[red]Error:       {document.error}[/red]")


@app.command("delete")
def delete(document_id: str = typer.Argument(..., help="Document ID")) -> None:
    """Delete a document and its stored file(s)."""
    ensure_db_ready()
    deleted = run(documents_service.delete_document(document_id))
    if deleted:
        console.print(f"[green]Deleted document[/green] {document_id}")
    else:
        console.print(f"[red]No such document[/red] {document_id}")
        raise typer.Exit(code=1)
