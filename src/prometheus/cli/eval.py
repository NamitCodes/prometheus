"""`research eval ...` commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from prometheus.cli._async import ensure_db_ready, run
from prometheus.evaluation.eval_runner import run_all

app = typer.Typer(help="Run the evaluation suite against the live chat workflow.")
console = Console()


@app.command("run")
def run_command() -> None:
    """Run the eval cases (real LLM calls; not part of `pytest`)."""
    ensure_db_ready()
    results = run(run_all())

    table = Table(title="Evaluation results")
    table.add_column("Case")
    table.add_column("Result")
    table.add_column("Details")
    for r in results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(r.case_name, status, "; ".join(r.failures) if r.failures else "")
    console.print(table)

    passed = sum(1 for r in results if r.passed)
    console.print(f"\n{passed}/{len(results)} passed")
    if passed < len(results):
        raise typer.Exit(code=1)
