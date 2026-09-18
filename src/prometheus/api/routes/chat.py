"""/api/v1/projects/{id}/chat -- mirrors `research chat ask` (see cli/chat.py).

Also exposes an SSE stream (new-plan.md Phase 16 / section 29): agent
activity, tool activity, answer tokens, and citations -- never raw
chain-of-thought. Stateless per request, same as `research chat ask` --
multi-turn persistence is new-plan.md section 27, still open (see plan.md
Phase 10 notes).
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from prometheus.api.schemas import ChatRequest, ChatResponse
from prometheus.services.projects import get_project
from prometheus.workflow.graph import ask, astream_chat

router = APIRouter(tags=["chat"])


@router.post("/projects/{project_id}/chat", response_model=ChatResponse)
async def chat_ask(project_id: str, request: ChatRequest) -> ChatResponse:
    if await get_project(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such project: {project_id}")

    try:
        result = await asyncio.to_thread(ask, project_id, request.question)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {exc}",
        ) from exc

    return ChatResponse(answer=result.answer, citations=result.citations)


@router.get("/projects/{project_id}/chat/stream")
async def chat_stream(project_id: str, question: str) -> StreamingResponse:
    """SSE endpoint. GET + a query param (not POST + body) because browsers'
    EventSource API only supports GET with no custom body."""
    if await get_project(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such project: {project_id}")

    async def event_stream():
        async for event in astream_chat(project_id, question):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
