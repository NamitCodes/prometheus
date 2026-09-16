"""
Vector store wrapper -- abstracts over ChromaDB / Qdrant so the rest of the
codebase doesn't care which backend is configured (see Settings.vector_db_backend).

TODO:
  - VectorStore protocol: add(chunks), query(embedding, top_k, filters), delete(ids)
  - ChromaVectorStore implementation (local, good for Phase 0-1 dev)
  - QdrantVectorStore implementation (swap in when scaling / deploying)
  - Metadata filters needed downstream: source_type, recency (date), project_id
"""
from __future__ import annotations

from typing import Any, Protocol


class VectorStore(Protocol):
    def add(self, chunks: list[dict]) -> None: ...
    def query(self, embedding: list[float], top_k: int, filters: dict | None = None) -> list[dict]: ...


def get_vector_store() -> Any:
    """Factory: returns Chroma or Qdrant impl based on settings.vector_db_backend."""
    raise NotImplementedError("Phase 1: implement vector store factory + backends")
