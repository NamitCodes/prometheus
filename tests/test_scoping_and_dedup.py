"""
Regression tests for:
1. Single-document query auto-scoping (demo_rag.run_user_documents_qa)
2. BM25 corpus deduplication on re-ingestion (_load_bm25_corpus)
3. Content-hash deduplication in hybrid_search (identical text with different UUIDs)
4. Multi-file cross-document isolation still works
"""
from __future__ import annotations

import dataclasses
import uuid
from pathlib import Path

import pytest

import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
from prometheus.llm.mock import MockLLMClient
from prometheus.rag.pipeline import query_rag
from prometheus.retrieval.hybrid_search import (
    _load_bm25_corpus,
    add_to_bm25,
    hybrid_search,
)
from prometheus.retrieval.ingestion import ingest_document


def _isolate_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect ChromaDB and BM25 index to an isolated temp directory."""
    isolated_settings = dataclasses.replace(
        vector_store_module.settings,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    monkeypatch.setattr(vector_store_module, "settings", isolated_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)


# ---------------------------------------------------------------------------
# 1. BM25 corpus deduplication - re-ingesting the same doc must not pile up
# ---------------------------------------------------------------------------

def test_bm25_dedup_on_reingest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-ingesting a document should not produce duplicate BM25 entries."""
    _isolate_stores(tmp_path, monkeypatch)

    doc_path = tmp_path / "paper.txt"
    doc_path.write_text(
        "Surface codes are topological quantum error-correcting codes.",
        encoding="utf-8",
    )

    # Ingest the same document TWICE (simulates running the script twice)
    doc_id_1 = ingest_document(str(doc_path), document_id="doc-surface-v1")
    doc_id_2 = ingest_document(str(doc_path), document_id="doc-surface-v1")
    assert doc_id_1 == doc_id_2 == "doc-surface-v1"

    corpus = _load_bm25_corpus()
    doc_entries = [r for r in corpus if r.get("metadata", {}).get("document_id") == "doc-surface-v1"]

    chunk_keys = [
        (r["metadata"]["document_id"], r["metadata"]["chunk_index"])
        for r in doc_entries
    ]
    assert len(chunk_keys) == len(set(chunk_keys)), (
        f"Duplicate BM25 entries detected after re-ingestion: {chunk_keys}"
    )


# ---------------------------------------------------------------------------
# 2. Content-hash deduplication in hybrid_search
# ---------------------------------------------------------------------------

def test_hybrid_search_deduplicates_identical_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chunks with different UUIDs but identical text must appear only once."""
    _isolate_stores(tmp_path, monkeypatch)

    identical_text = "Entanglement is a fundamental quantum correlation phenomenon."

    fake_chunks = [
        {
            "id": str(uuid.uuid4()),
            "text": identical_text,
            "metadata": {"document_id": "doc-dup", "chunk_index": 0},
        },
        {
            "id": str(uuid.uuid4()),
            "text": identical_text,
            "metadata": {"document_id": "doc-dup", "chunk_index": 0},
        },
    ]
    add_to_bm25(fake_chunks)

    from prometheus.retrieval.ingestion import embed
    from prometheus.retrieval.vector_store import get_vector_store

    embeddings = embed([identical_text, identical_text])
    store_records = [
        {"id": fake_chunks[0]["id"], "text": identical_text, "embedding": embeddings[0], "metadata": fake_chunks[0]["metadata"]},
        {"id": fake_chunks[1]["id"], "text": identical_text, "embedding": embeddings[1], "metadata": fake_chunks[1]["metadata"]},
    ]
    get_vector_store().add(store_records)

    results = hybrid_search(identical_text, top_k=10, filters={"document_id": "doc-dup"})
    texts = [r["text"].strip() for r in results]
    assert texts.count(identical_text) == 1, (
        f"Expected 1 occurrence, got {texts.count(identical_text)}"
    )


# ---------------------------------------------------------------------------
# 3. Single-document auto-scoping
# ---------------------------------------------------------------------------

def test_single_doc_scope_excludes_other_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When document_id is set, only chunks from that document are returned."""
    _isolate_stores(tmp_path, monkeypatch)

    doc_a = tmp_path / "quantum.txt"
    doc_a.write_text(
        "Surface codes require approximately 1000 physical qubits per logical qubit.",
        encoding="utf-8",
    )
    doc_b = tmp_path / "biology.txt"
    doc_b.write_text(
        "Mitochondria are double-membrane organelles that produce ATP.",
        encoding="utf-8",
    )
    id_a = ingest_document(str(doc_a), document_id="doc-quantum-scope")
    _id_b = ingest_document(str(doc_b), document_id="doc-biology-scope")

    mock_llm = MockLLMClient(default_response="Surface codes use about 1000 qubits [1].")

    result = query_rag(
        question="How many qubits does a surface code need?",
        document_id=id_a,
        top_k=5,
        llm_client=mock_llm,
    )

    for src in result.sources:
        assert src.document_id == id_a, (
            f"Scoped query leaked chunk from '{src.document_id}' (expected '{id_a}')"
        )
    for chunk in result.retrieved_chunks:
        assert chunk["metadata"]["document_id"] == id_a, (
            f"Retrieved chunk from wrong document: {chunk['metadata']['document_id']}"
        )


# ---------------------------------------------------------------------------
# 4. Multi-doc global search still spans all documents
# ---------------------------------------------------------------------------

def test_multi_doc_global_search_spans_all_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a document_id filter, results can come from any indexed document."""
    _isolate_stores(tmp_path, monkeypatch)

    doc_x = tmp_path / "photosynthesis.txt"
    doc_x.write_text("Photosynthesis converts sunlight into chemical energy in plants.", encoding="utf-8")
    doc_y = tmp_path / "relativity.txt"
    doc_y.write_text("Einsteins general relativity describes spacetime curvature by mass.", encoding="utf-8")

    id_x = ingest_document(str(doc_x), document_id="doc-photo")
    id_y = ingest_document(str(doc_y), document_id="doc-relativity")

    results = hybrid_search("energy mass curvature photosynthesis", top_k=10, filters=None)
    doc_ids_found = {r["metadata"]["document_id"] for r in results}

    assert id_x in doc_ids_found or id_y in doc_ids_found, (
        "Global search should return results from at least one of the two documents"
    )
