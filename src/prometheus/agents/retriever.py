"""
Retriever Agent

Responsibility (per proposal, Section 2 & 3):
  Queries the four data stores (paper corpus, domain docs, Findings DB,
  vector store) using hybrid search (BM25 + dense embeddings), reranks with
  a cross-encoder, and filters by recency and source credibility. Routes
  each sub-question dynamically to whichever store(s) best answer it.

TODO:
  - Define def retriever_node(state: GraphState) -> GraphState
  - Wire in prometheus.retrieval.hybrid_search.hybrid_search(...)
  - Implement routing logic: sub-question -> which store(s) to hit
  - Attach provenance (source, url/doi, retrieval score) to every chunk returned
"""
from __future__ import annotations

from typing import Any


def retriever_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node. Reads state["query"] (from Researcher), writes
    state["retrieved_chunks"] with provenance + scores attached."""
    raise NotImplementedError("Phase 2: implement Retriever Agent")
