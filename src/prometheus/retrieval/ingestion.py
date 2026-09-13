"""
Ingestion pipeline: raw paper/doc -> parsed text -> chunks -> embeddings ->
vector store + BM25 index.

Covers both data sources described in the proposal:
  - Paper corpus (PDFs fetched via arXiv/S2/OpenAlex, parsed with PyMuPDF)
  - Project/domain docs (user-uploaded specs/documentation)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from sentence_transformers import SentenceTransformer

from prometheus.retrieval import hybrid_search
from prometheus.retrieval.vector_store import get_vector_store

# Pinned embedding model: small, fast, good enough for Phase 1-2 dev.
# Revisit alongside the reranker model choice once quality tuning starts.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 800  # chars
CHUNK_OVERLAP = 100  # chars

_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def parse_pdf(path: str) -> str:
    with pymupdf.open(path) as doc:
        return "\n\n".join(page.get_text() for page in doc)


def chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Recursive-ish splitter: break on paragraphs first, packing them into
    ~`size`-char windows with `overlap` chars of trailing context carried
    into the next chunk; falls back to a hard split for any oversized
    paragraph."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(paragraph), size - overlap):
                chunks.append(paragraph[i : i + size])
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_embedding_model()
    return model.encode(texts, convert_to_numpy=True).tolist()


def _make_chunk_records(texts: list[str], metadata: dict) -> list[dict]:
    embeddings = embed(texts)
    ingested_at = datetime.now(UTC).isoformat()
    return [
        {
            "id": str(uuid.uuid4()),
            "text": text,
            "embedding": embedding,
            "metadata": {**metadata, "ingested_at": ingested_at},
        }
        for text, embedding in zip(texts, embeddings)
    ]


def ingest_paper(pdf_path: str, source_id: str) -> None:
    text = parse_pdf(pdf_path)
    texts = chunk(text)
    records = _make_chunk_records(
        texts,
        metadata={"source_type": "paper", "source_id": source_id, "url": pdf_path},
    )
    get_vector_store().add(records)
    hybrid_search.add_to_bm25(records)


def ingest_domain_doc(path: str, project_id: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    texts = chunk(text)
    records = _make_chunk_records(
        texts,
        metadata={"source_type": "domain_doc", "project_id": project_id, "url": path},
    )
    get_vector_store().add(records)
    hybrid_search.add_to_bm25(records)
