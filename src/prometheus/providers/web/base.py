"""Web access provider interfaces (new-plan.md section 21).

Three distinct capabilities, kept separate per the plan: searching the web,
fetching one URL's content, and crawling outward from a starting URL.
"""
from __future__ import annotations

from typing import Protocol, TypedDict


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


class FetchedPage(TypedDict):
    url: str
    title: str
    text: str
    links: list[str]


class WebSearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class WebFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class WebCrawlerProvider(Protocol):
    def crawl(self, start_url: str, max_pages: int = 10, max_depth: int = 2) -> list[FetchedPage]: ...
