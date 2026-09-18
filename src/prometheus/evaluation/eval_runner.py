"""
Runs EVAL_CASES against the real chat workflow (new-plan.md Phase 14):
checks routing (right tool family used, and *not* used when it shouldn't
be -- over-triggering web search is as much a failure as under-triggering)
and a keyword-grounding check on the answer.

Runs against your real OPENROUTER_MODEL -- this is a live LLM eval, not a
mocked unit test, and is deliberately kept out of the default `pytest` run
(slow, costs tokens, not fully deterministic). Creates and cleans up
throwaway `eval-*` projects.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from prometheus.evaluation.dataset import EVAL_CASES, EvalCase
from prometheus.services.documents import add_document
from prometheus.services.projects import create_project, delete_project
from prometheus.tasks.celery_app import celery_app
from prometheus.workflow.graph import ask


@dataclass
class EvalResult:
    case_name: str
    passed: bool
    answer: str
    failures: list[str] = field(default_factory=list)


async def _setup_project(case: EvalCase) -> str:
    project = await create_project(f"eval-{case.name}")
    with tempfile.TemporaryDirectory() as tmp_dir:
        for filename, content in case.setup_documents:
            path = Path(tmp_dir) / filename
            path.write_text(content)
            document = await add_document(project.id, str(path))

            from prometheus.tasks.document_tasks import process_document

            # Force synchronous processing regardless of the ambient Celery
            # config, so the eval doesn't race a real worker.
            was_eager = celery_app.conf.task_always_eager
            celery_app.conf.task_always_eager = True
            try:
                process_document.delay(document.id)
            finally:
                celery_app.conf.task_always_eager = was_eager
    return project.id


def _run_case(case: EvalCase, project_id: str) -> EvalResult:
    result = ask(project_id, case.question)
    failures: list[str] = []

    used_document_tool = any(c.get("type") == "document" for c in result.citations)
    used_web_tool = any(c.get("type") == "web" for c in result.citations)

    if case.expects_document_tool and not used_document_tool:
        failures.append("expected knowledge_search to be used (no document citation found)")
    if not case.expects_document_tool and used_document_tool:
        failures.append("knowledge_search used but not expected (over-triggering)")
    if case.expects_web_tool and not used_web_tool:
        failures.append("expected web_search/web_fetch to be used (no web citation found)")
    if not case.expects_web_tool and used_web_tool:
        failures.append("web tool used but not expected (over-triggering)")

    if case.expected_keyword.lower() not in result.answer.lower():
        failures.append(f"expected keyword {case.expected_keyword!r} not found in the answer")

    return EvalResult(case_name=case.name, passed=not failures, answer=result.answer, failures=failures)


async def run_all(cases: list[EvalCase] | None = None) -> list[EvalResult]:
    results = []
    for case in cases if cases is not None else EVAL_CASES:
        project_id = await _setup_project(case)
        try:
            results.append(_run_case(case, project_id))
        finally:
            await delete_project(project_id)
    return results
