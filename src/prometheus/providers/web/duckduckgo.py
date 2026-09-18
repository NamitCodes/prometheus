"""DuckDuckGo search provider -- TEMPORARY, see plan.md Phase 11.

Uses `ddgs`, which scrapes DuckDuckGo's HTML/lite endpoints (no official
API, no key required). This can break or get rate-limited without notice.
Chosen only because the user has no card for Tavily/Brave's signup; replace
with `BraveSearchProvider` (same `WebSearchProvider` interface) once an
account is available.
"""
from __future__ import annotations

from ddgs import DDGS

from prometheus.providers.web.base import SearchResult


class DuckDuckGoSearchProvider:
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        with DDGS() as ddgs:
            raw_results = ddgs.text(query, max_results=max_results)

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw_results
        ]
