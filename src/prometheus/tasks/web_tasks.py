"""Persistent web crawling/indexing task (new-plan.md section 30-32).

A crawled page becomes just another indexed knowledge source, scoped to the
requesting project -- same retrieval path as an uploaded document, just
without a Document row/stored file (there's no local file to track).
"""
from __future__ import annotations

import logging

from prometheus.providers.web import get_web_crawler
from prometheus.retrieval.ingestion import ingest_web_page
from prometheus.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="web.crawl_and_index")
def crawl_and_index(
    project_id: str,
    start_url: str,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> dict:
    pages = get_web_crawler().crawl(start_url, max_pages=max_pages, max_depth=max_depth)

    for page in pages:
        ingest_web_page(
            url=page["url"],
            title=page["title"],
            text=page["text"],
            metadata={"project_id": project_id},
        )

    logger.info("crawl_and_index: indexed %d page(s) from %s into project %s", len(pages), start_url, project_id)
    return {"pages_indexed": len(pages), "urls": [p["url"] for p in pages]}
