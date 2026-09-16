"""
OpenAlex API client (free, no key -- use the "polite pool" via mailto).

TODO:
  - GET https://api.openalex.org/works?search=...&mailto=<settings.openalex_mailto>
  - Normalize response fields to the shared PaperRecord shape
"""
from __future__ import annotations


def search_openalex(query: str, max_results: int = 20) -> list[dict]:
    raise NotImplementedError("Phase 1: implement OpenAlex search")
