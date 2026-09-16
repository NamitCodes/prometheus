"""
Unit tests for the Prometheus RAG generation pipeline.
Covers:
1. Retrieval -> context construction & citation numbering
2. Context construction -> prompt formatting
3. RAG pipeline execution with Mock LLM
4. Source metadata preservation (document_id, filename, page_number)
5. Document isolation (filtering by document_id)
6. Insufficient context handling
7. Minimal FastAPI endpoints
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
from prometheus.api.app import app
from prometheus.llm.mock import MockLLMClient
from prometheus.rag.context import build_context
from prometheus.rag.pipeline import INSUFFICIENT_CONTEXT_MESSAGE, query_rag
from prometheus.rag.prompts import RAG_SYSTEM_PROMPT, build_rag_user_prompt
from prometheus.retrieval.ingestion import ingest_document


def _isolate_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate ChromaDB and BM25 persistent files to a clean temporary directory for testing."""
    isolated_settings = dataclasses.replace(
        vector_store_module.settings,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    monkeypatch.setattr(vector_store_module, "settings", isolated_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)


# ---------------------------------------------------------------------------
# 1. Context Construction & Citation Attribution
# ---------------------------------------------------------------------------

def test_context_construction_formats_numbered_citations():
    mock_chunks = [
        {
            "id": "c-101",
            "text": "First evidence passage regarding Transformer attention.",
            "metadata": {
                "document_id": "doc-vaswani",
                "filename": "attention_is_all_you_need.pdf",
                "file_type": "pdf",
                "page_number": 3,
                "heading": "3.1 Scaled Dot-Product Attention",
            },
            "score": 0.95,
        },
        {
            "id": "c-102",
            "text": "Second passage describing multi-head mechanics.",
            "metadata": {
                "document_id": "doc-vaswani",
                "filename": "attention_is_all_you_need.pdf",
                "file_type": "pdf",
                "page_number": 4,
            },
            "score": 0.88,
        },
    ]

    context_str, sources = build_context(mock_chunks)

    assert "[1] Source: attention_is_all_you_need.pdf (Page 3, Section: '3.1 Scaled Dot-Product Attention') [DocID: doc-vaswani]" in context_str
    assert "[2] Source: attention_is_all_you_need.pdf (Page 4) [DocID: doc-vaswani]" in context_str
    assert len(sources) == 2

    assert sources[0].citation_index == 1
    assert sources[0].document_id == "doc-vaswani"
    assert sources[0].filename == "attention_is_all_you_need.pdf"
    assert sources[0].page_number == 3
    assert sources[0].score == 0.95
    assert "First evidence passage" in sources[0].text_snippet

    assert sources[1].citation_index == 2
    assert sources[1].page_number == 4


# ---------------------------------------------------------------------------
# 2. Context -> Prompt Formatting
# ---------------------------------------------------------------------------

def test_rag_prompt_formatting():
    context_str = "[1] Source: paper.pdf (Page 1) [DocID: doc-1]\nEvidence content."
    question = "How does attention scale?"
    user_prompt = build_rag_user_prompt(question, context_str)

    assert "Context Evidence:" in user_prompt
    assert context_str in user_prompt
    assert "User Question:" in user_prompt
    assert question in user_prompt
    assert "Answer:" in user_prompt


# ---------------------------------------------------------------------------
# 3. RAG Pipeline with Mock LLM
# ---------------------------------------------------------------------------

def test_rag_pipeline_with_mock_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc_path = tmp_path / "research_notes.txt"
    doc_path.write_text(
        "Prometheus implements a hybrid search architecture combining dense vectors and BM25.\n\n"
        "The cross-encoder reranker scores candidate passages for precision.",
        encoding="utf-8",
    )

    doc_id = ingest_document(str(doc_path), document_id="doc-prom-1")

    mock_llm = MockLLMClient(
        default_response="Prometheus combines dense vector search with BM25 and reranking [1]."
    )

    result = query_rag(
        question="What search architecture does Prometheus use?",
        document_id=doc_id,
        top_k=3,
        llm_client=mock_llm,
    )

    assert result.has_sufficient_context is True
    assert "Prometheus combines dense vector search" in result.answer
    assert len(result.sources) >= 1
    assert result.sources[0].document_id == doc_id
    assert result.sources[0].filename == "research_notes.txt"
    assert len(mock_llm.call_history) == 1
    assert mock_llm.call_history[0]["system_prompt"] == RAG_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 4. Source Metadata Preservation
# ---------------------------------------------------------------------------

def test_source_metadata_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _isolate_stores(tmp_path, monkeypatch)

    import pymupdf

    pdf_path = tmp_path / "quantum.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Qubits exist in superposition states on page one.")
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Quantum decoherence causes decay into classical states on page two.")
    doc.save(str(pdf_path))
    doc.close()

    doc_id = ingest_document(str(pdf_path), document_id="doc-quantum-42")

    mock_llm = MockLLMClient(default_response="Superposition allows qubits to exist in multiple states [1].")

    result = query_rag(
        question="What state do qubits exist in?",
        document_id=doc_id,
        top_k=2,
        llm_client=mock_llm,
    )

    assert len(result.sources) >= 1
    first_source = result.sources[0]
    assert first_source.document_id == "doc-quantum-42"
    assert first_source.filename == "quantum.pdf"
    assert first_source.page_number in (1, 2)
    assert first_source.citation_index == 1


# ---------------------------------------------------------------------------
# 5. Document Isolation (No Cross-Document Leakage)
# ---------------------------------------------------------------------------

def test_document_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc_a = tmp_path / "biology.txt"
    doc_a.write_text("Mitochondria are the powerhouses of biological cells.", encoding="utf-8")
    id_a = ingest_document(str(doc_a), document_id="doc-biology")

    doc_b = tmp_path / "astronomy.txt"
    doc_b.write_text("Supernovae are explosive stellar deaths producing neutron stars.", encoding="utf-8")
    id_b = ingest_document(str(doc_b), document_id="doc-astronomy")

    mock_llm = MockLLMClient(default_response="Mitochondria generate cellular energy [1].")

    # Search strictly within doc-biology for supernovae
    res_bio = query_rag(
        question="What are supernovae?",
        document_id=id_a,
        top_k=5,
        llm_client=mock_llm,
    )

    # All retrieved chunks MUST belong strictly to doc-biology, NEVER doc-astronomy
    for src in res_bio.sources:
        assert src.document_id == id_a
        assert src.document_id != id_b

    for chunk in res_bio.retrieved_chunks:
        assert chunk["metadata"]["document_id"] == id_a
        assert chunk["metadata"]["document_id"] != id_b


# ---------------------------------------------------------------------------
# 6. Insufficient Context Handling
# ---------------------------------------------------------------------------

def test_insufficient_context_handling_empty_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _isolate_stores(tmp_path, monkeypatch)

    mock_llm = MockLLMClient()
    result = query_rag(
        question="What is the capital of Mars?",
        document_id="nonexistent-doc",
        llm_client=mock_llm,
    )

    assert result.has_sufficient_context is False
    assert result.answer == INSUFFICIENT_CONTEXT_MESSAGE
    assert result.sources == []
    # LLM should not be called when zero candidate chunks are found
    assert len(mock_llm.call_history) == 0


# ---------------------------------------------------------------------------
# 7. Minimal FastAPI Endpoints
# ---------------------------------------------------------------------------

def test_api_health():
    client = TestClient(app)
    response = client.get("/api/rag/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "prometheus-rag"}


def test_api_query_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _isolate_stores(tmp_path, monkeypatch)

    # Ingest document
    doc_path = tmp_path / "api_test.txt"
    doc_path.write_text("FastAPI provides lightning-fast ASGI performance.", encoding="utf-8")
    doc_id = ingest_document(str(doc_path), document_id="doc-api-1")

    # Patch global LLM client with Mock
    mock_llm = MockLLMClient(default_response="FastAPI is fast [1].")
    monkeypatch.setattr("prometheus.rag.pipeline.get_llm_client", lambda: mock_llm)

    client = TestClient(app)
    payload = {
        "question": "How is FastAPI's performance?",
        "document_id": doc_id,
        "top_k": 3,
    }
    response = client.post("/api/rag/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["document_id"] == doc_id
