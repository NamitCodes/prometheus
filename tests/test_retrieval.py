"""
Unit tests for the retrieval layer: source clients, hybrid search,
reranking, and routing.
"""
import dataclasses

import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
from prometheus.retrieval.hybrid_search import bm25_search, dense_search, hybrid_search, route
from prometheus.retrieval.ingestion import ingest_domain_doc

SAMPLE_DOC = (
    "Retrieval-augmented generation grounds language model outputs in "
    "retrieved evidence rather than parametric memory alone."
)


def _isolate_stores(tmp_path, monkeypatch):
    isolated_settings = dataclasses.replace(vector_store_module.settings, chroma_persist_dir=str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store_module, "settings", isolated_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)


def test_hybrid_search_merges_bm25_and_dense_results(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc_path = tmp_path / "doc.txt"
    doc_path.write_text(SAMPLE_DOC, encoding="utf-8")
    ingest_domain_doc(str(doc_path), project_id="test-project")

    bm25_hits = bm25_search("retrieval augmented generation")
    dense_hits = dense_search("retrieval augmented generation")
    merged = hybrid_search("retrieval augmented generation")

    assert bm25_hits, "expected at least one BM25 hit"
    assert dense_hits, "expected at least one dense hit"
    assert merged, "expected at least one merged hit"
    assert merged[0]["text"] == SAMPLE_DOC
    assert all("score" in hit for hit in merged)


def test_route_sends_recall_query_to_findings_db():
    assert "findings_db" in route("have we looked at this hypothesis before?")
    assert "findings_db" not in route("what is the effect of temperature on accuracy?")
    assert set(route("what is the effect of temperature on accuracy?")) == {"paper_corpus", "domain_docs"}
