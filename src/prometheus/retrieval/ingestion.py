"""
Ingestion pipeline: raw paper/doc -> parsed text -> chunks -> embeddings ->
vector store + BM25 index.

Covers both data sources described in the proposal:
  - Paper corpus (PDFs fetched via arXiv/S2/OpenAlex, parsed with PyMuPDF)
  - Project/domain docs (user-uploaded specs/documentation)

TODO:
  - parse_pdf(path) -> str                          (use PyMuPDF / fitz)
  - chunk(text, strategy="recursive", size=..., overlap=...) -> list[Chunk]
  - embed(chunks) -> attach vectors (sentence-transformers model, pick + pin one)
  - upsert into vector store (prometheus.retrieval.vector_store) AND
    into the BM25 index (prometheus.retrieval.hybrid_search)
  - Store chunk-level provenance: source_type, source_id, url/doi, ingested_at
"""
from __future__ import annotations


def ingest_paper(pdf_path: str, source_id: str) -> None:
    raise NotImplementedError("Phase 1: implement paper ingestion")


def ingest_domain_doc(path: str, project_id: str) -> None:
    raise NotImplementedError("Phase 1: implement domain doc ingestion")
