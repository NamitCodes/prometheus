"""Breadth-first crawler bounded by page count and depth, restricted to the
starting URL's domain (new-plan.md section 58: limit pages, limit depth,
limit per-domain requests). Fetch failures are skipped, not fatal to the
whole crawl.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from prometheus.config import settings
from prometheus.providers.web.base import FetchedPage, WebFetcher

logger = logging.getLogger(__name__)


class SimpleWebCrawler:
    def __init__(self, fetcher: WebFetcher) -> None:
        self._fetcher = fetcher

    def crawl(
        self,
        start_url: str,
        max_pages: int | None = None,
        max_depth: int | None = None,
    ) -> list[FetchedPage]:
        max_pages = max_pages if max_pages is not None else settings.web_crawl_max_pages
        max_depth = max_depth if max_depth is not None else settings.web_crawl_max_depth
        start_domain = urlparse(start_url).netloc

        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_url, 0)]
        pages: list[FetchedPage] = []

        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                page = self._fetcher.fetch(url)
            except Exception:
                logger.warning("crawl: failed to fetch %s, skipping", url, exc_info=True)
                continue
            pages.append(page)

            if depth >= max_depth:
                continue

            for link in page["links"]:
                if link not in visited and urlparse(link).netloc == start_domain:
                    queue.append((link, depth + 1))

        return pages
