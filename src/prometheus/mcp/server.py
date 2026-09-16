"""
MCP server exposing Prometheus's persistence layer to external clients
(per proposal, Section 4: "exposed through MCP tools ... for
interoperability with external clients").

TODO:
  - search_papers(query: str, top_k: int = 10) -> list[dict]
      wraps prometheus.retrieval.hybrid_search.hybrid_search
  - save_report(report: dict) -> str
      wraps prometheus.findings.repository.save_report
  - Register both as MCP tools and serve on settings.mcp_server_port
"""
from __future__ import annotations


def create_mcp_server() -> Any:  # noqa: F821 - Any imported lazily once mcp SDK is wired in
    raise NotImplementedError("Phase 4: implement MCP server + tool registration")
