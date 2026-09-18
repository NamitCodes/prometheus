"""
Unit tests for the application workspace layer (projects/documents) added
for new-plan.md's CLI-first architecture -- service functions the CLI calls
into, backed by an isolated async SQLite DB per test.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import prometheus.db.session as db_session
import prometheus.services.documents as documents_service
import prometheus.services.projects as projects_service
from prometheus.db.base import Base
from prometheus.db.models import Document  # noqa: F401  -- registers on Base.metadata


@pytest_asyncio.fixture
async def isolated_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test_app.db")
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_local)
    monkeypatch.setattr(projects_service, "AsyncSessionLocal", session_local)
    monkeypatch.setattr(documents_service, "AsyncSessionLocal", session_local)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_local
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_list_projects(isolated_db):
    created = await projects_service.create_project("RAG survey", description="lit review")
    assert created.id

    projects = await projects_service.list_projects()
    assert [p.name for p in projects] == ["RAG survey"]


@pytest.mark.asyncio
async def test_delete_project(isolated_db):
    created = await projects_service.create_project("temp project")
    assert await projects_service.delete_project(created.id) is True
    assert await projects_service.list_projects() == []
    assert await projects_service.delete_project(created.id) is False


@pytest.mark.asyncio
async def test_list_documents_empty(isolated_db):
    project = await projects_service.create_project("empty project")
    assert await documents_service.list_documents(project_id=project.id) == []
