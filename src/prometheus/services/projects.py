"""Project application service."""
from __future__ import annotations

from sqlalchemy import select

from prometheus.db.models import Project
from prometheus.db.session import AsyncSessionLocal
from prometheus.retrieval import hybrid_search
from prometheus.retrieval.vector_store import get_vector_store


async def create_project(name: str, description: str = "") -> Project:
    async with AsyncSessionLocal() as session:
        project = Project(name=name, description=description)
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def list_projects() -> list[Project]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())


async def get_project(project_id: str) -> Project | None:
    async with AsyncSessionLocal() as session:
        return await session.get(Project, project_id)


async def delete_project(project_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            return False
        await session.delete(project)
        await session.commit()

    # Purge in one shot by project_id -- covers uploaded-document chunks AND
    # web-crawled chunks, which have no Document row to loop over individually.
    get_vector_store().delete_by_metadata({"project_id": project_id})
    hybrid_search.remove_from_bm25_by_metadata({"project_id": project_id})
    return True
