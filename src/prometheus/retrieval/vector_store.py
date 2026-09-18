"""
Vector store wrapper -- abstracts over ChromaDB / Qdrant so the rest of the
codebase doesn't care which backend is configured (see Settings.VECTOR_DB_BACKEND).

Chroma is the Phase 0-2 default (local, zero-infra). Qdrant support is
deferred until scaling/deployment needs it (see docs/architecture.md).
"""
from __future__ import annotations

from typing import Protocol

import chromadb

from prometheus.config import settings

_COLLECTION_NAME = "prometheus_chunks"


def _build_where(filters: dict | None) -> dict | None:
    """ChromaDB requires a `where` dict to have exactly one top-level key --
    multiple equality filters (e.g. project_id + document_id) must be
    combined with an explicit $and."""
    if not filters:
        return None
    if len(filters) == 1:
        return filters
    return {"$and": [{key: value} for key, value in filters.items()]}


class VectorStore(Protocol):
    def add(self, chunks: list[dict]) -> None: ...
    def query(self, embedding: list[float], top_k: int, filters: dict | None = None) -> list[dict]: ...
    def delete(self, ids: list[str]) -> None: ...
    def delete_by_metadata(self, filters: dict) -> None: ...


class ChromaVectorStore:
    """chunks: [{id, text, embedding, metadata: {source_type, source_id, url, project_id, ingested_at, ...}}]

    Chroma's embedded PersistentClient is single-process by design --
    concurrent processes (a Celery prefork pool, `uvicorn --reload`'s worker,
    a one-off script) opening the same persist_dir at once can corrupt or
    error out ("readonly database", "Nothing found on disk", "Error finding
    id"). If `server_url` is set, this connects to a real `chroma run`
    server instead (HttpClient), which is safe for concurrent access;
    PersistentClient remains the zero-infra default for solo local dev.
    """

    def __init__(self, persist_dir: str, server_url: str | None = None) -> None:
        if server_url:
            host, _, port = server_url.partition(":")
            self._client = chromadb.HttpClient(host=host or "localhost", port=int(port or 8000))
        else:
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
            where=_build_where(filters),
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

    def delete_by_metadata(self, filters: dict) -> None:
        where = _build_where(filters)
        if where:
            self._collection.delete(where=where)


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Factory: returns Chroma or Qdrant impl based on settings.VECTOR_DB_BACKEND."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    if settings.VECTOR_DB_BACKEND == "chroma":
        _vector_store = ChromaVectorStore(settings.CHROMA_PERSIST_DIR, server_url=settings.CHROMA_SERVER_URL or None)
    elif settings.VECTOR_DB_BACKEND == "qdrant":
        raise NotImplementedError("Qdrant backend not implemented yet; set VECTOR_DB_BACKEND=chroma")
    else:
        raise ValueError(f"Unknown VECTOR_DB_BACKEND: {settings.VECTOR_DB_BACKEND!r}")
    return _vector_store
