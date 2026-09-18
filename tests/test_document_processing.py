"""
Tests for the Celery document-processing pipeline (new-plan.md Phase 4):
status transitions and vector-store indexing, run in-process via Celery's
`task_always_eager` (no broker/worker required).
"""
from __future__ import annotations

import dataclasses

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import prometheus.db.session as db_session
import prometheus.providers.storage as storage_module
import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
import prometheus.services.documents as documents_service
import prometheus.services.projects as projects_service
from prometheus.db.base import Base
from prometheus.db.models import Document, DocumentVersion  # noqa: F401
from prometheus.retrieval.hybrid_search import bm25_search
from prometheus.services.documents import DocumentValidationError
from prometheus.tasks.celery_app import celery_app


@pytest_asyncio.fixture
async def isolated_env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test_app.db")
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_local)
    monkeypatch.setattr(projects_service, "AsyncSessionLocal", session_local)
    monkeypatch.setattr(documents_service, "AsyncSessionLocal", session_local)

    import prometheus.tasks.document_tasks as document_tasks_module

    monkeypatch.setattr(document_tasks_module, "AsyncSessionLocal", session_local)

    storage_settings = dataclasses.replace(
        storage_module.settings, document_storage_dir=str(tmp_path / "storage")
    )
    monkeypatch.setattr(storage_module, "settings", storage_settings)
    monkeypatch.setattr(storage_module, "_provider", None)

    vector_settings = dataclasses.replace(
        vector_store_module.settings, chroma_persist_dir=str(tmp_path / "chroma")
    )
    monkeypatch.setattr(vector_store_module, "settings", vector_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", vector_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield tmp_path
    await engine.dispose()


@pytest.mark.asyncio
async def test_add_and_process_document_reaches_ready(isolated_env, tmp_path):
    project = await projects_service.create_project("Processing project")
    source = tmp_path / "notes.txt"
    source.write_text("Retrieval-augmented generation grounds answers in retrieved evidence.")

    document = await documents_service.add_and_process_document(project.id, str(source))

    refreshed = await documents_service.get_document(document.id)
    assert refreshed.status == "READY"
    assert refreshed.error is None


@pytest.mark.asyncio
async def test_reprocess_document_requires_existing_document(isolated_env):
    with pytest.raises(DocumentValidationError, match="no such document"):
        await documents_service.reprocess_document("does-not-exist")


@pytest.mark.asyncio
async def test_process_document_retries_transient_store_errors(isolated_env, tmp_path, monkeypatch):
    """ChromaDB's embedded store can transiently collide under concurrent
    worker processes ('readonly database' / 'database is locked'). That
    should trigger a Celery retry rather than marking the document FAILED.

    Note: with `task_eager_propagates=True` (needed so permanent failures
    surface in the test below), Celery's eager mode raises `Retry` directly
    instead of looping through it -- the actual retry-then-redeliver cycle
    only runs in a real worker process. This test verifies the part that
    *is* observable at this level: a transient error requests a retry and
    does not mark the document FAILED.
    """
    from celery.exceptions import Retry

    import prometheus.tasks.document_tasks as document_tasks_module

    project = await projects_service.create_project("Retry project")
    source = tmp_path / "notes.txt"
    source.write_text("some content")
    document = await documents_service.add_document(project.id, str(source))

    def flaky_ingest(*args, **kwargs):
        raise RuntimeError("Database error: (code: 1032) attempt to write a readonly database")

    monkeypatch.setattr(document_tasks_module, "ingest_document", flaky_ingest)

    with pytest.raises(Retry):
        document_tasks_module.process_document.delay(document.id)

    refreshed = await documents_service.get_document(document.id)
    assert refreshed.status != "FAILED"


@pytest.mark.asyncio
async def test_process_document_does_not_retry_permanent_errors(isolated_env, tmp_path, monkeypatch):
    """A genuinely broken file shouldn't burn through retries -- fail fast."""
    import prometheus.tasks.document_tasks as document_tasks_module

    project = await projects_service.create_project("Permanent failure project")
    source = tmp_path / "notes.txt"
    source.write_text("some content")
    document = await documents_service.add_document(project.id, str(source))

    call_count = {"n": 0}

    def always_fail(*args, **kwargs):
        call_count["n"] += 1
        raise ValueError("corrupt file, not a real document")

    monkeypatch.setattr(document_tasks_module, "ingest_document", always_fail)

    with pytest.raises(ValueError, match="corrupt file"):
        document_tasks_module.process_document.delay(document.id)

    refreshed = await documents_service.get_document(document.id)
    assert refreshed.status == "FAILED"
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_reprocess_document_is_idempotent(isolated_env, tmp_path):
    """Reprocessing must purge the document's old chunks first -- otherwise
    stale and fresh chunks from each run pile up together in the index."""
    project = await projects_service.create_project("Reprocess project")
    source = tmp_path / "notes.txt"
    source.write_text("Retrieval-augmented generation grounds answers in retrieved evidence.")

    document = await documents_service.add_and_process_document(project.id, str(source))
    first_run_hits = len(bm25_search("retrieval augmented generation"))

    await documents_service.reprocess_document(document.id)
    second_run_hits = len(bm25_search("retrieval augmented generation"))

    assert second_run_hits == first_run_hits, (
        "reprocessing the same unchanged document should not accumulate duplicate chunks"
    )
