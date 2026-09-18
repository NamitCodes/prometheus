"""/api/v1/projects/{id}/search -- mirrors `research search knowledge` (see cli/search.py)."""
from __future__ import annotations

from fastapi import APIRouter

from prometheus.api.schemas import SearchRequest
from prometheus.services.retrieval import RetrievedChunk, search_knowledge

router = APIRouter(tags=["search"])


@router.post("/projects/{project_id}/search", response_model=list[RetrievedChunk])
async def search_project_knowledge(project_id: str, request: SearchRequest) -> list[RetrievedChunk]:
    return await search_knowledge(
        request.query,
        project_id=project_id,
        document_id=request.document_id,
        limit=request.limit,
    )
