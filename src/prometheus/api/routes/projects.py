"""/api/v1/projects -- mirrors `research project ...` (see cli/project.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from prometheus.api.schemas import ProjectCreateRequest, ProjectResponse
from prometheus.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(request: ProjectCreateRequest) -> ProjectResponse:
    project = await projects_service.create_project(name=request.name, description=request.description)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects() -> list[ProjectResponse]:
    projects = await projects_service.list_projects()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    project = await projects_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such project: {project_id}")
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str) -> None:
    deleted = await projects_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such project: {project_id}")
