"""
arXiv client (free API, no key required).

TODO:
  - GET http://export.arxiv.org/api/query with search_query params
  - Parse Atom XML response -> list[PaperRecord]
  - Respect arXiv's rate-limit guidance (3s between requests)
"""
from __future__ import annotations


def search_arxiv(query: str, max_results: int = 20) -> list[dict]:
    raise NotImplementedError("Phase 1: implement arXiv search")
