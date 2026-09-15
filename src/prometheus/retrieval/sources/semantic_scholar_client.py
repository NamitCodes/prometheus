"""
Semantic Scholar Academic Graph API client.

GET https://api.semanticscholar.org/graph/v1/paper/search. Uses
SEMANTIC_SCHOLAR_API_KEY (settings.SEMANTIC_SCHOLAR_API_KEY) if set, for a
higher rate limit.
"""
from __future__ import annotations

import httpx

from prometheus.config import settings
from prometheus.retrieval.sources.paper_record import PaperRecord

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,year,authors,externalIds,url,openAccessPdf"


def search_semantic_scholar(query: str, max_results: int = 20) -> list[PaperRecord]:
    headers = {"User-Agent": "prometheus-research-agent/0.1 (mailto:research@example.com)"}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    params = {"query": query, "limit": max_results, "fields": _FIELDS}
    response = httpx.get(SEMANTIC_SCHOLAR_API_URL, params=params, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json().get("data", [])
    return [_to_record(paper) for paper in data]


def _to_record(paper: dict) -> PaperRecord:
    external_ids = paper.get("externalIds") or {}
    open_access_pdf = paper.get("openAccessPdf") or {}
    authors = [a["name"] for a in paper.get("authors") or [] if a.get("name")]

    return PaperRecord(
        source="semantic_scholar",
        source_id=paper["paperId"],
        title=paper.get("title") or "",
        abstract=paper.get("abstract"),
        authors=authors,
        year=paper.get("year"),
        doi=external_ids.get("DOI"),
        url=paper.get("url"),
        pdf_url=open_access_pdf.get("url"),
    )
