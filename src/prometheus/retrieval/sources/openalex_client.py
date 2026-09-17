"""
OpenAlex API client (free, no key -- use the "polite pool" via mailto).

GET https://api.openalex.org/works?search=...&mailto=<settings.OPENALEX_MAILTO>
"""
from __future__ import annotations

import re

import httpx

from prometheus.config import settings
from prometheus.retrieval.sources.paper_record import PaperRecord

OPENALEX_API_URL = "https://api.openalex.org/works"


def search_openalex(query: str, max_results: int = 20) -> list[PaperRecord]:
    clean_query = re.sub(r"[?*+\[\]{}\\^~:|]", " ", query or "").strip()
    clean_query = re.sub(r"\s+", " ", clean_query)
    if not clean_query:
        return []

    params = {"search": clean_query, "per_page": max_results}
    if settings.OPENALEX_MAILTO:
        params["mailto"] = settings.OPENALEX_MAILTO

    response = httpx.get(OPENALEX_API_URL, params=params, timeout=30.0)
    response.raise_for_status()
    results = response.json().get("results", [])
    return [_to_record(work) for work in results]


def _to_record(work: dict) -> PaperRecord:
    authors = [
        a["author"]["display_name"]
        for a in work.get("authorships") or []
        if a.get("author", {}).get("display_name")
    ]
    open_access = work.get("open_access") or {}
    primary_location = work.get("primary_location") or {}
    doi = work.get("doi")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]

    return PaperRecord(
        source="openalex",
        source_id=work["id"].rsplit("/", 1)[-1],
        title=work.get("display_name") or work.get("title") or "",
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        authors=authors,
        year=work.get("publication_year"),
        doi=doi,
        url=work.get("id"),
        pdf_url=primary_location.get("pdf_url") or open_access.get("oa_url"),
    )


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, indices in inverted_index.items():
        for i in indices:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))
