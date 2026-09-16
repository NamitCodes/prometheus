"""
Hybrid search: combines BM25 lexical search with dense vector search, then
hands the merged candidate set to the reranker. Also owns the routing
logic that decides which store(s) a given sub-question should query.

TODO:
  - BM25 index build/query (rank_bm25, kept in sync with ingestion.py)
  - dense_search(query) via vector_store.get_vector_store().query(...)
  - merge/dedupe BM25 + dense candidate sets before reranking
  - route(sub_question) -> list[store_name] -- e.g. keyword/entity heavy ->
    paper corpus + domain docs; "have we looked at this before" -> Findings DB
"""
from __future__ import annotations


def hybrid_search(query: str, top_k: int = 20, filters: dict | None = None) -> list[dict]:
    raise NotImplementedError("Phase 1: implement BM25 + dense hybrid search")


def route(sub_question: str) -> list[str]:
    raise NotImplementedError("Phase 1: implement store routing logic")
