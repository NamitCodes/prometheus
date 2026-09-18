"""HTTP web fetcher: validated GET + HTML text/link extraction.

Redirects are followed manually (not via httpx's `follow_redirects=True`)
so every hop gets the SSRF check, not just the initial URL -- a public URL
could still redirect to an internal address.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from prometheus.config import settings
from prometheus.providers.web.base import FetchedPage
from prometheus.providers.web.security import validate_public_url

_USER_AGENT = "prometheus-research-agent/0.1"
_MAX_REDIRECTS = 5


class HttpWebFetcher:
    def fetch(self, url: str) -> FetchedPage:
        response = self._get_following_redirects(url)
        response.raise_for_status()
        content = response.content[: settings.web_fetch_max_bytes]

        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else str(response.url)
        text = " ".join(soup.get_text(separator=" ").split())
        links = self._extract_links(soup, base_url=str(response.url))

        return {"url": str(response.url), "title": title, "text": text, "links": links}

    def _get_following_redirects(self, url: str) -> httpx.Response:
        current_url = url
        for _ in range(_MAX_REDIRECTS):
            validate_public_url(current_url)
            with httpx.Client(
                follow_redirects=False, timeout=settings.web_fetch_timeout_seconds
            ) as client:
                response = client.get(current_url, headers={"User-Agent": _USER_AGENT})

            if not response.is_redirect:
                return response

            location = response.headers.get("location")
            if not location:
                return response
            current_url = str(httpx.URL(current_url).join(location))

        raise httpx.TooManyRedirects(f"exceeded {_MAX_REDIRECTS} redirects fetching {url}")

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].split("#", 1)[0].strip()
            if not href or href.startswith("javascript:"):
                continue
            absolute = str(httpx.URL(base_url).join(href))
            if absolute not in seen and absolute.startswith(("http://", "https://")):
                seen.add(absolute)
                links.append(absolute)
        return links
