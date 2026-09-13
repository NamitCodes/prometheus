"""
Vector store wrapper -- abstracts over ChromaDB / Qdrant so the rest of the
codebase doesn't care which backend is configured (see Settings.vector_db_backend).

Chroma is the Phase 0-2 default (local, zero-infra). Qdrant support is
deferred until scaling/deployment needs it (see docs/architecture.md).
"""
from __future__ import annotations

from typing import Protocol

import chromadb

from prometheus.config import settings

_COLLECTION_NAME = "prometheus_chunks"


class VectorStore(Protocol):
    def add(self, chunks: list[dict]) -> None: ...
    def query(self, embedding: list[float], top_k: int, filters: dict | None = None) -> list[dict]: ...
    def delete(self, ids: list[str]) -> None: ...


class ChromaVectorStore:
    """chunks: [{id, text, embedding, metadata: {source_type, source_id, url, project_id, ingested_at, ...}}]"""

    def __init__(self, persist_dir: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(_COLLECTION_NAME)

    def add(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c.get("metadata", {}) for c in chunks],
        )

    def query(self, embedding: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filters or None,
        )
        hits = []
        ids = result.get("ids") or [[]]
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        for i in range(len(ids[0])):
            hits.append(
                {
                    "id": ids[0][i],
                    "text": documents[0][i],
                    "metadata": metadatas[0][i],
                    "distance": distances[0][i],
                }
            )
        return hits

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Factory: returns Chroma or Qdrant impl based on settings.vector_db_backend."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    if settings.vector_db_backend == "chroma":
        _vector_store = ChromaVectorStore(settings.chroma_persist_dir)
    elif settings.vector_db_backend == "qdrant":
        raise NotImplementedError("Qdrant backend not implemented yet; set VECTOR_DB_BACKEND=chroma")
    else:
        raise ValueError(f"Unknown VECTOR_DB_BACKEND: {settings.vector_db_backend!r}")
    return _vector_store
