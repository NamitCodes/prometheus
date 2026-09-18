"""Document processing task: parse -> chunk -> embed -> index.

Only `document_id` crosses the Redis queue (new-plan.md section 31) -- the
worker loads everything else (storage key, project id) from the database.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor

from prometheus.db.models import Document
from prometheus.db.session import AsyncSessionLocal
from prometheus.providers.storage import get_storage_provider
from prometheus.retrieval import hybrid_search
from prometheus.retrieval.ingestion import ingest_document
from prometheus.retrieval.vector_store import get_vector_store
from prometheus.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ChromaDB's embedded PersistentClient is single-process by design (see
# plan.md Phase 11/12 notes) -- concurrent Celery worker processes writing
# to the same store can transiently collide with a "readonly database" /
# "database is locked" error. It usually clears once the other writer
# finishes, so retry a few times before giving up.
_TRANSIENT_STORE_ERROR_MARKERS = ("readonly database", "database is locked")


def _is_transient_store_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _TRANSIENT_STORE_ERROR_MARKERS)


def _run_async[T](coro: Awaitable[T]) -> T:
    """`asyncio.run` from a normal Celery worker thread (no loop running).
    In eager-mode tests, the caller may already be inside a running loop --
    run the coroutine in its own thread with a fresh loop instead, since
    `asyncio.run` cannot nest inside one."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _load_document(document_id: str) -> Document | None:
    async with AsyncSessionLocal() as session:
        return await session.get(Document, document_id)


async def _set_status(document_id: str, status: str, error: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = status
        document.error = error
        await session.commit()


@celery_app.task(name="documents.process_document", bind=True, max_retries=4, default_retry_delay=5)
def process_document(self, document_id: str) -> None:
    document = _run_async(_load_document(document_id))
    if document is None:
        logger.warning("process_document: no such document %s", document_id)
        return

    if not document.storage_path:
        _run_async(_set_status(document_id, "FAILED", "document has no stored file"))
        return

    _run_async(_set_status(document_id, "PROCESSING"))
    try:
        abs_path = get_storage_provider().abs_path(document.storage_path)
        _run_async(_set_status(document_id, "INDEXING"))

        # Idempotency: purge any chunks from a previous run (e.g. a reindex)
        # before re-adding, otherwise stale and fresh chunks pile up together.
        get_vector_store().delete_by_metadata({"document_id": document_id})
        hybrid_search.remove_from_bm25(document_id)

        ingest_document(
            str(abs_path),
            document_id=document_id,
            metadata={"project_id": document.project_id},
        )
        _run_async(_set_status(document_id, "READY"))
    except Exception as exc:
        if _is_transient_store_error(exc) and self.request.retries < self.max_retries:
            countdown = 5 * (self.request.retries + 1)
            logger.warning(
                "process_document: transient store-lock error for %s (attempt %d/%d), "
                "retrying in %ds: %s",
                document_id,
                self.request.retries + 1,
                self.max_retries,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown) from exc

        logger.exception("process_document failed for %s", document_id)
        _run_async(_set_status(document_id, "FAILED", str(exc)))
        raise
