"""
Tests for services.retrieval.search_knowledge (new-plan.md Phase 5/7):
project scoping, document filtering, and empty-result behavior. The
public signature requires `project_id` and exposes no raw `filters`
override, so cross-project leakage isn't just tested against -- it's
structurally impossible to request.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
from prometheus.retrieval.ingestion import ingest_document
from prometheus.services.retrieval import search_knowledge


def _isolate_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_settings = dataclasses.replace(
        vector_store_module.settings, chroma_persist_dir=str(tmp_path / "chroma")
    )
    monkeypatch.setattr(vector_store_module, "settings", isolated_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)


@pytest.mark.asyncio
async def test_search_knowledge_scopes_by_project(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc_a = tmp_path / "project_a.txt"
    doc_a.write_text("Quantum surface codes require redundant physical qubits.", encoding="utf-8")
    doc_b = tmp_path / "project_b.txt"
    doc_b.write_text("Quantum surface codes are used in fault-tolerant computing.", encoding="utf-8")

    ingest_document(str(doc_a), document_id="doc-a", metadata={"project_id": "project-a"})
    ingest_document(str(doc_b), document_id="doc-b", metadata={"project_id": "project-b"})

    results = await search_knowledge("quantum surface codes", project_id="project-a", limit=10)

    assert results, "expected at least one result scoped to project-a"
    assert all(r.project_id == "project-a" for r in results)
    assert all(r.document_id != "doc-b" for r in results)


@pytest.mark.asyncio
async def test_search_knowledge_document_filter_combines_with_project(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc_x = tmp_path / "doc_x.txt"
    doc_x.write_text("Mitochondria produce ATP through oxidative phosphorylation.", encoding="utf-8")
    doc_y = tmp_path / "doc_y.txt"
    doc_y.write_text("Chloroplasts produce ATP through photosynthesis.", encoding="utf-8")

    ingest_document(str(doc_x), document_id="doc-x", metadata={"project_id": "shared-project"})
    ingest_document(str(doc_y), document_id="doc-y", metadata={"project_id": "shared-project"})

    results = await search_knowledge(
        "ATP production", project_id="shared-project", document_id="doc-x", limit=10
    )

    assert results
    assert all(r.document_id == "doc-x" for r in results)


@pytest.mark.asyncio
async def test_search_knowledge_empty_when_no_matching_project(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc = tmp_path / "doc.txt"
    doc.write_text("Some indexed content about penguins.", encoding="utf-8")
    ingest_document(str(doc), document_id="doc-1", metadata={"project_id": "project-1"})

    results = await search_knowledge("penguins", project_id="nonexistent-project", limit=10)
    assert results == []
