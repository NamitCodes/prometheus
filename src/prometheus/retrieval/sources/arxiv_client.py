"""
arXiv client (free API, no key required).

GET http://export.arxiv.org/api/query with search_query params, parses the
Atom XML response into PaperRecords. Respects arXiv's rate-limit guidance
(callers doing multiple searches should space them ~3s apart).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from prometheus.retrieval.sources.paper_record import PaperRecord

ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def search_arxiv(query: str, max_results: int = 20) -> list[PaperRecord]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
    }
    response = httpx.get(ARXIV_API_URL, params=params, timeout=30.0)
    response.raise_for_status()
    return _parse_feed(response.text)


def _parse_feed(xml_text: str) -> list[PaperRecord]:
    root = ET.fromstring(xml_text)
    records = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        arxiv_id = _text(entry, "id").rsplit("/", 1)[-1]
        title = " ".join(_text(entry, "title").split())
        abstract = " ".join(_text(entry, "summary").split()) or None
        authors = [
            _text(author, "name")
            for author in entry.findall(f"{_ATOM_NS}author")
            if _text(author, "name")
        ]
        published = _text(entry, "published")
        year = int(published[:4]) if published[:4].isdigit() else None

        pdf_url = None
        abs_url = None
        for link in entry.findall(f"{_ATOM_NS}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
            elif link.get("rel") == "alternate":
                abs_url = link.get("href")

        records.append(
            PaperRecord(
                source="arxiv",
                source_id=arxiv_id,
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                doi=None,
                url=abs_url,
                pdf_url=pdf_url,
            )
        )
    return records


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(f"{_ATOM_NS}{tag}")
    return (child.text or "").strip() if child is not None else ""
