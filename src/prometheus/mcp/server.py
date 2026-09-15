"""
MCP server exposing Prometheus's persistence layer to external clients
(per proposal, Section 4: "exposed through MCP tools ... for
interoperability with external clients").

TODO:
  - search_papers(query: str, top_k: int = 10) -> list[dict]
      wraps prometheus.retrieval.hybrid_search.hybrid_search
  - save_report(report: dict) -> str
      wraps prometheus.findings.repository.save_report
  - Register both as MCP tools and serve on settings.MCP_SERVER_PORT
"""
from __future__ import annotations

from typing import Any


def create_mcp_server() -> Any:
    raise NotImplementedError("Phase 4: implement MCP server + tool registration")
