"""
Tests for SimpleWebCrawler's bounds (new-plan.md section 58: limit pages,
limit depth, stay on-domain), driven by a fake WebFetcher (no real network).
"""
from __future__ import annotations

from prometheus.providers.web.crawler import SimpleWebCrawler


class FakeFetcher:
    """A tiny fake site graph: pages map to (text, links)."""

    def __init__(self, pages: dict[str, tuple[str, list[str]]]):
        self._pages = pages

    def fetch(self, url: str) -> dict:
        if url not in self._pages:
            raise ValueError(f"404: {url}")
        text, links = self._pages[url]
        return {"url": url, "title": url, "text": text, "links": links}


def test_crawl_stays_within_max_depth():
    pages = {
        "https://a.test/": ("root", ["https://a.test/p1"]),
        "https://a.test/p1": ("depth1", ["https://a.test/p2"]),
        "https://a.test/p2": ("depth2", ["https://a.test/p3"]),
        "https://a.test/p3": ("depth3", []),
    }
    fetcher = FakeFetcher(pages)
    crawler = SimpleWebCrawler(fetcher)

    result = crawler.crawl("https://a.test/", max_pages=10, max_depth=1)

    urls = {p["url"] for p in result}
    assert urls == {"https://a.test/", "https://a.test/p1"}


def test_crawl_stops_at_max_pages():
    pages = {f"https://a.test/p{i}": (f"page {i}", [f"https://a.test/p{i + 1}"]) for i in range(20)}
    pages["https://a.test/"] = ("root", ["https://a.test/p0"])
    fetcher = FakeFetcher(pages)
    crawler = SimpleWebCrawler(fetcher)

    result = crawler.crawl("https://a.test/", max_pages=3, max_depth=100)

    assert len(result) == 3


def test_crawl_does_not_follow_offsite_links():
    pages = {
        "https://a.test/": ("root", ["https://evil.test/p1", "https://a.test/p1"]),
        "https://a.test/p1": ("onsite", []),
        "https://evil.test/p1": ("offsite -- should never be fetched", []),
    }
    fetcher = FakeFetcher(pages)
    crawler = SimpleWebCrawler(fetcher)

    result = crawler.crawl("https://a.test/", max_pages=10, max_depth=5)

    urls = {p["url"] for p in result}
    assert urls == {"https://a.test/", "https://a.test/p1"}


def test_crawl_skips_pages_that_fail_to_fetch():
    pages = {
        "https://a.test/": ("root", ["https://a.test/broken", "https://a.test/p1"]),
        "https://a.test/p1": ("ok", []),
        # "https://a.test/broken" intentionally absent -> fetch() raises
    }
    fetcher = FakeFetcher(pages)
    crawler = SimpleWebCrawler(fetcher)

    result = crawler.crawl("https://a.test/", max_pages=10, max_depth=5)

    urls = {p["url"] for p in result}
    assert urls == {"https://a.test/", "https://a.test/p1"}
