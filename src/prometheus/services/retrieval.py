"""Knowledge retrieval application service (new-plan.md section 19-20).

`search_knowledge` is the one place project scoping is enforced: `project_id`
is a required keyword argument merged into the filters *after* any
caller-supplied filters, so a caller can never override it. Retrieval must
never rely on the LLM/agent layer to keep results inside project
boundaries (new-plan.md section 21) -- this function is the boundary.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from prometheus.retrieval.hybrid_search import hybrid_search
from prometheus.retrieval.reranker import apply_recency_and_credibility_filters, rerank


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str | None = None
    project_id: str | None = None
    filename: str | None = None
    page_number: int | None = None
    slide_number: int | None = None
    text: str
    score: float


def _to_retrieved_chunk(candidate: dict) -> RetrievedChunk:
    metadata = candidate.get("metadata", {}) or {}
    score = candidate.get("final_score", candidate.get("rerank_score", candidate.get("score", 0.0)))
    return RetrievedChunk(
        chunk_id=candidate["id"],
        document_id=metadata.get("document_id"),
        project_id=metadata.get("project_id"),
        filename=metadata.get("filename"),
        page_number=metadata.get("page_number"),
        slide_number=metadata.get("slide_number"),
        text=candidate.get("text", ""),
        score=float(score),
    )


async def search_knowledge(
    query: str,
    *,
    project_id: str,
    document_id: str | None = None,
    limit: int = 10,
) -> list[RetrievedChunk]:
    """Hybrid search + rerank, scoped to `project_id` (and optionally a
    single `document_id`), returning structured, provenance-carrying results."""
    filters: dict = {}
    if document_id is not None:
        filters["document_id"] = document_id
    filters["project_id"] = project_id  # always applied last -- cannot be overridden

    def _run() -> list[dict]:
        candidates = hybrid_search(query, top_k=max(limit * 3, 20), filters=filters)
        if not candidates:
            return []
        reranked = rerank(query, candidates)
        return apply_recency_and_credibility_filters(reranked)[:limit]

    results = await asyncio.to_thread(_run)
    return [_to_retrieved_chunk(r) for r in results]
