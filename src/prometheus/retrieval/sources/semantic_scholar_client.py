"""
Semantic Scholar Academic Graph API client.

TODO:
  - GET https://api.semanticscholar.org/graph/v1/paper/search
  - Use SEMANTIC_SCHOLAR_API_KEY (settings.semantic_scholar_api_key) if set,
    for a higher rate limit
  - Normalize response fields to the shared PaperRecord shape
"""
from __future__ import annotations


def search_semantic_scholar(query: str, max_results: int = 20) -> list[dict]:
    raise NotImplementedError("Phase 1: implement Semantic Scholar search")
