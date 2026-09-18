"""
Tests for the /api/v1 routes (new-plan.md Phase 15): same isolation pattern
as the CLI/service tests, driven through FastAPI's TestClient so this
exercises the actual HTTP layer (schemas, status codes, file upload)
rather than just the services underneath.
"""
from __future__ import annotations

import dataclasses

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import prometheus.db.session as db_session
import prometheus.providers.storage as storage_module
import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
import prometheus.services.documents as documents_service
import prometheus.services.projects as projects_service
from prometheus.api.app import app
from prometheus.db.base import Base
from prometheus.db.models import Document, DocumentVersion  # noqa: F401
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


@pytest.fixture
def client(isolated_env):
    return TestClient(app)


def test_project_crud(client):
    create_resp = client.post("/api/v1/projects", json={"name": "API project", "description": "test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    assert project["name"] == "API project"

    list_resp = client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    assert [p["id"] for p in list_resp.json()] == [project["id"]]

    get_resp = client.get(f"/api/v1/projects/{project['id']}")
    assert get_resp.status_code == 200

    delete_resp = client.delete(f"/api/v1/projects/{project['id']}")
    assert delete_resp.status_code == 204

    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404


def test_get_nonexistent_project_returns_404(client):
    assert client.get("/api/v1/projects/does-not-exist").status_code == 404


def test_document_upload_and_lifecycle(client):
    project = client.post("/api/v1/projects", json={"name": "Doc project"}).json()

    upload_resp = client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert upload_resp.status_code == 201
    document = upload_resp.json()
    assert document["filename"] == "notes.txt"
    assert document["project_id"] == project["id"]

    list_resp = client.get(f"/api/v1/projects/{project['id']}/documents")
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/api/v1/documents/{document['id']}")
    assert get_resp.status_code == 200

    delete_resp = client.delete(f"/api/v1/documents/{document['id']}")
    assert delete_resp.status_code == 204
    assert client.get(f"/api/v1/documents/{document['id']}").status_code == 404


def test_document_upload_sanitizes_path_traversal_filename(client):
    """file.filename is client-controlled -- a crafted name must not let the
    upload write outside the storage directory."""
    project = client.post("/api/v1/projects", json={"name": "Traversal project"}).json()

    upload_resp = client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("../../../etc/evil.txt", b"malicious", "text/plain")},
    )
    assert upload_resp.status_code == 201
    document = upload_resp.json()
    assert document["filename"] == "evil.txt"
    assert ".." not in document["filename"]


def test_document_upload_rejects_unsupported_extension(client):
    project = client.post("/api/v1/projects", json={"name": "Bad ext project"}).json()

    upload_resp = client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("virus.exe", b"binary", "application/octet-stream")},
    )
    assert upload_resp.status_code == 400


def test_search_returns_ingested_chunks(client):
    project = client.post("/api/v1/projects", json={"name": "Search project"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("notes.txt", b"Photosynthesis converts sunlight into chemical energy.", "text/plain")},
    )

    search_resp = client.post(
        f"/api/v1/projects/{project['id']}/search",
        json={"query": "photosynthesis", "limit": 5},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert results
    assert results[0]["project_id"] == project["id"]


def test_chat_rejects_unknown_project(client):
    resp = client.post("/api/v1/projects/does-not-exist/chat", json={"question": "hello"})
    assert resp.status_code == 404


def test_chat_returns_grounded_answer(client, monkeypatch):
    project = client.post("/api/v1/projects", json={"name": "Chat project"}).json()

    def fake_ask(project_id, question, llm=None):
        from prometheus.workflow.graph import ChatResult

        return ChatResult(answer="mocked answer", citations=[{"type": "document", "chunk_id": "c1"}])

    monkeypatch.setattr("prometheus.api.routes.chat.ask", fake_ask)

    resp = client.post(f"/api/v1/projects/{project['id']}/chat", json={"question": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "mocked answer"
    assert body["citations"] == [{"type": "document", "chunk_id": "c1"}]
