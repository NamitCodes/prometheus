"""
Findings DB repository -- read/write access used by:
  - Retriever Agent (query past findings as a data store)
  - Meta-Orchestrator (persist final report + reasoning chain on approval)
  - MCP tools (search_papers / save_report expose a subset of this)

TODO:
  - save_report(report: Report) -> str (id)
  - get_report(report_id: str) -> Report | None
  - search_findings(query: str, top_k: int) -> list[Report]  (hybrid search
    over past reports, same machinery as prometheus.retrieval.hybrid_search)
  - save_reasoning_chain(report_id: str, steps: list[ReasoningStep]) -> None
"""
from __future__ import annotations


def save_report(report: dict) -> str:
    raise NotImplementedError("Phase 1/4: implement Findings DB writes")


def search_findings(query: str, top_k: int = 10) -> list[dict]:
    raise NotImplementedError("Phase 1/4: implement Findings DB search")
