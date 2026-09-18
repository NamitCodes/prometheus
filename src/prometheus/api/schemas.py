"""Pydantic request/response models for the /api/v1 routes."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    status: str
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str
    document_id: str | None = None
    limit: int = 10


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]
