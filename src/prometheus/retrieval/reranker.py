"""
Cross-encoder reranker: takes the union of BM25 + dense-vector hits and
re-scores (query, chunk) pairs jointly for a sharper final ranking.

TODO:
  - Pick + pin a cross-encoder model (e.g. a sentence-transformers CrossEncoder)
  - rerank(query, candidates) -> candidates sorted by cross-encoder score
  - Recency + source-credibility filtering/boosting happens after rerank,
    per the proposal ("followed by ... filtering by recency and source
    credibility")
"""
from __future__ import annotations


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    raise NotImplementedError("Phase 1: implement cross-encoder reranking")


def apply_recency_and_credibility_filters(candidates: list[dict]) -> list[dict]:
    raise NotImplementedError("Phase 1: implement recency/credibility filtering")
