"""Document application service.

`add_document` validates, stores the file, and records UPLOADED metadata.
`add_and_process_document` additionally enqueues the Celery pipeline
(parse -> chunk -> embed -> index, new-plan.md Phase 4) that carries the
document through PROCESSING -> INDEXING -> READY/FAILED.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from prometheus.config import settings
from prometheus.db.models import Document, DocumentVersion
from prometheus.db.session import AsyncSessionLocal
from prometheus.providers.storage import get_storage_provider
from prometheus.retrieval import hybrid_search
from prometheus.retrieval.parsers import SUPPORTED_EXTENSIONS
from prometheus.retrieval.vector_store import get_vector_store
from prometheus.services.projects import get_project


class DocumentValidationError(ValueError):
    """Raised when an uploaded file fails validation (format, size, existence)."""


async def add_document(project_id: str, file_path: str) -> Document:
    project = await get_project(project_id)
    if project is None:
        raise DocumentValidationError(f"no such project: {project_id}")

    source = Path(file_path)
    if not source.is_file():
        raise DocumentValidationError(f"file not found: {file_path}")

    ext = source.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError(
            f"unsupported file format {ext!r}. Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    size_bytes = source.stat().st_size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise DocumentValidationError(
            f"file is {size_bytes / (1024 * 1024):.1f}MB, exceeds the "
            f"{settings.max_upload_size_mb}MB limit"
        )

    async with AsyncSessionLocal() as session:
        document = Document(project_id=project_id, filename=source.name, status="UPLOADED")
        session.add(document)
        await session.flush()  # assigns document.id

        storage_key = f"{project_id}/{document.id}/v1/{source.name}"
        get_storage_provider().save(source, storage_key)

        document.storage_path = storage_key
        session.add(
            DocumentVersion(
                document_id=document.id,
                version_number=1,
                storage_key=storage_key,
                original_filename=source.name,
                size_bytes=size_bytes,
            )
        )

        await session.commit()
        await session.refresh(document)
        return document


async def add_and_process_document(project_id: str, file_path: str) -> Document:
    """`add_document` plus enqueuing the async processing pipeline."""
    from prometheus.tasks.document_tasks import process_document

    document = await add_document(project_id, file_path)
    process_document.delay(document.id)
    return document


async def reprocess_document(document_id: str) -> Document:
    """Re-enqueue processing for a document that's already stored (e.g. after a FAILED run)."""
    from prometheus.tasks.document_tasks import process_document

    document = await get_document(document_id)
    if document is None:
        raise DocumentValidationError(f"no such document: {document_id}")
    if not document.storage_path:
        raise DocumentValidationError(f"document {document_id} has no stored file to reprocess")

    process_document.delay(document.id)
    return document


async def get_document(document_id: str) -> Document | None:
    async with AsyncSessionLocal() as session:
        return await session.get(Document, document_id)


async def list_documents(project_id: str | None = None) -> list[Document]:
    async with AsyncSessionLocal() as session:
        stmt = select(Document).order_by(Document.created_at.desc())
        if project_id is not None:
            stmt = stmt.where(Document.project_id == project_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def delete_document(document_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return False

        storage = get_storage_provider()
        result = await session.execute(
            select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        )
        for version in result.scalars().all():
            storage.delete(version.storage_key)

        await session.delete(document)
        await session.commit()

    # Purge any indexed chunks so deleted documents don't linger in search
    # results (vector store + BM25 are separate stores from the app DB above).
    get_vector_store().delete_by_metadata({"document_id": document_id})
    hybrid_search.remove_from_bm25(document_id)
    return True
