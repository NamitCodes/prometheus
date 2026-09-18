"""Web access provider factories."""
from __future__ import annotations

from prometheus.providers.web.base import WebCrawlerProvider, WebFetcher, WebSearchProvider
from prometheus.providers.web.crawler import SimpleWebCrawler
from prometheus.providers.web.duckduckgo import DuckDuckGoSearchProvider
from prometheus.providers.web.fetcher import HttpWebFetcher

_search_provider: WebSearchProvider | None = None
_fetcher: WebFetcher | None = None
_crawler: WebCrawlerProvider | None = None


def get_web_search_provider() -> WebSearchProvider:
    global _search_provider
    if _search_provider is None:
        _search_provider = DuckDuckGoSearchProvider()
    return _search_provider


def get_web_fetcher() -> WebFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = HttpWebFetcher()
    return _fetcher


def get_web_crawler() -> WebCrawlerProvider:
    global _crawler
    if _crawler is None:
        _crawler = SimpleWebCrawler(get_web_fetcher())
    return _crawler
