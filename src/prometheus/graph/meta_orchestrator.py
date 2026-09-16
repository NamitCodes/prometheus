"""
Meta-Orchestrator graph.

Responsibility (per proposal, Section 3):
  Takes the researcher's broad, open-ended question, decomposes it into
  sub-questions, and spawns one sub-orchestrator per sub-question
  (recursively -- a sub-orchestrator's own findings may spawn further
  sub-questions). Aggregates sub-orchestrator reports into the final
  report (confidence levels + open objections) and hands it to the human
  researcher for approval/redirection at each checkpoint. Saves the full
  reasoning chain to the Findings DB for reuse.

TODO:
  - Define def decompose(question: str) -> list[str] (LLM call)
  - Fan out: invoke build_sub_orchestrator_graph() per sub-question
    (consider async/parallel execution with a concurrency cap)
  - Recursion policy: when does a sub-orchestrator's output spawn more
    sub-questions vs. terminate?
  - Aggregate sub-reports into one Report (see prometheus.findings.models.Report)
  - Human-in-the-loop checkpoint before finalizing the report
  - On approval: persist reasoning chain via prometheus.findings.repository
"""
from __future__ import annotations

from typing import Any


def build_meta_orchestrator_graph() -> Any:
    """Returns a compiled LangGraph graph for the top-level question."""
    raise NotImplementedError("Phase 3: build the meta-orchestrator StateGraph")


def run_investigation(question: str) -> dict[str, Any]:
    """Entry point: broad question in, final Report + human checkpoint out."""
    raise NotImplementedError("Phase 3: wire meta-orchestrator end to end")
