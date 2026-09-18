"""/api/v1/... documents -- mirrors `research document ...` (see cli/document.py)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from prometheus.api.schemas import DocumentResponse
from prometheus.services import documents as documents_service
from prometheus.services.documents import DocumentValidationError

router = APIRouter(tags=["documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_document(
    project_id: str,
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    # file.filename is client-controlled -- strip any directory components
    # (e.g. "../../etc/passwd") before using it as a path segment. `.name`
    # alone isn't enough: Path("..").name == ".." itself, still a traversal.
    filename = Path(file.filename or "").name
    if filename in ("", ".", ".."):
        filename = "uploaded_document"

    # A plain NamedTemporaryFile would give the file a random name, and
    # add_document() takes the filename from the path it's handed -- so the
    # original upload name would be lost. Use a real directory instead so
    # the temp path's basename is the actual filename.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / filename
        with tmp_path.open("wb") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)

        try:
            document = await documents_service.add_and_process_document(project_id, str(tmp_path))
        except DocumentValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DocumentResponse.model_validate(document)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_documents(project_id: str) -> list[DocumentResponse]:
    documents = await documents_service.list_documents(project_id=project_id)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    document = await documents_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such document: {document_id}")
    return DocumentResponse.model_validate(document)


@router.post("/documents/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(document_id: str) -> DocumentResponse:
    try:
        document = await documents_service.reprocess_document(document_id)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentResponse.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str) -> None:
    deleted = await documents_service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such document: {document_id}")
