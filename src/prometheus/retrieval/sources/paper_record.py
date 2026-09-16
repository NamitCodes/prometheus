"""
Shared normalized shape that every paper-source client returns, so the rest
of the retrieval layer (ingestion, dedup, hybrid search) doesn't need to know
which upstream API a given paper came from.
"""
from __future__ import annotations

from pydantic import BaseModel


class PaperRecord(BaseModel):
    source: str  # "arxiv" | "semantic_scholar" | "openalex"
    source_id: str  # id as used by that source (arXiv id, S2 paperId, OpenAlex work id)
    title: str
    abstract: str | None = None
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
