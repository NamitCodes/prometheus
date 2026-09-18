"""
Unit tests for document upload/storage (new-plan.md Phase 3): validation,
local object storage, and the delete path -- isolated DB + isolated
storage dir per test.
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
from prometheus.services.documents import DocumentValidationError
from prometheus.services.retrieval import search_knowledge
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


async def _make_project():
    return await projects_service.create_project("Doc project")


@pytest.mark.asyncio
async def test_add_document_stores_file_and_records_metadata(isolated_env, tmp_path):
    project = await _make_project()
    source = tmp_path / "notes.txt"
    source.write_text("hello world")

    document = await documents_service.add_document(project.id, str(source))

    assert document.status == "UPLOADED"
    assert document.filename == "notes.txt"
    assert document.storage_path is not None

    stored_path = storage_module.get_storage_provider().abs_path(document.storage_path)
    assert stored_path.exists()
    assert stored_path.read_text() == "hello world"


@pytest.mark.asyncio
async def test_add_document_rejects_unknown_project(isolated_env, tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("hello")

    with pytest.raises(DocumentValidationError, match="no such project"):
        await documents_service.add_document("does-not-exist", str(source))


@pytest.mark.asyncio
async def test_add_document_rejects_unsupported_extension(isolated_env, tmp_path):
    project = await _make_project()
    source = tmp_path / "notes.exe"
    source.write_text("hello")

    with pytest.raises(DocumentValidationError, match="unsupported file format"):
        await documents_service.add_document(project.id, str(source))


@pytest.mark.asyncio
async def test_add_document_rejects_oversized_file(isolated_env, tmp_path, monkeypatch):
    isolated_settings = dataclasses.replace(storage_module.settings, max_upload_size_mb=0)
    monkeypatch.setattr(documents_service, "settings", isolated_settings)

    project = await _make_project()
    source = tmp_path / "notes.txt"
    source.write_text("this file is definitely bigger than zero megabytes")

    with pytest.raises(DocumentValidationError, match="exceeds"):
        await documents_service.add_document(project.id, str(source))


@pytest.mark.asyncio
async def test_delete_document_removes_row_and_file(isolated_env, tmp_path):
    project = await _make_project()
    source = tmp_path / "notes.txt"
    source.write_text("hello")

    document = await documents_service.add_document(project.id, str(source))
    stored_path = storage_module.get_storage_provider().abs_path(document.storage_path)
    assert stored_path.exists()

    assert await documents_service.delete_document(document.id) is True
    assert not stored_path.exists()
    assert await documents_service.list_documents(project_id=project.id) == []
    assert await documents_service.delete_document(document.id) is False


@pytest.mark.asyncio
async def test_delete_document_purges_search_index(isolated_env, tmp_path):
    """A deleted document's chunks must not linger in the vector store/BM25
    index -- otherwise search would leak content the user explicitly removed."""
    project = await _make_project()
    source = tmp_path / "notes.txt"
    source.write_text("Photosynthesis converts sunlight into chemical energy in plant cells.")

    document = await documents_service.add_and_process_document(project.id, str(source))
    assert (await documents_service.get_document(document.id)).status == "READY"

    before = await search_knowledge("photosynthesis", project_id=project.id)
    assert before, "expected the ingested chunk to be searchable before deletion"

    assert await documents_service.delete_document(document.id) is True

    after = await search_knowledge("photosynthesis", project_id=project.id)
    assert after == []


@pytest.mark.asyncio
async def test_delete_project_purges_search_index(isolated_env, tmp_path):
    """Deleting a project must purge its chunks too -- otherwise every
    project deletion leaks orphaned, unbounded-growing index entries,
    including web-crawled chunks that have no Document row at all."""
    project = await _make_project()
    source = tmp_path / "notes.txt"
    source.write_text("Mitochondria produce ATP through oxidative phosphorylation.")
    await documents_service.add_and_process_document(project.id, str(source))

    before = await search_knowledge("mitochondria ATP", project_id=project.id)
    assert before, "expected the ingested chunk to be searchable before project deletion"

    assert await projects_service.delete_project(project.id) is True

    after = await search_knowledge("mitochondria ATP", project_id=project.id)
    assert after == []
