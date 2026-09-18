"""Celery application. Run a worker with:

    celery -A prometheus.tasks.celery_app worker --loglevel=info

`task_always_eager` runs tasks synchronously in-process (no broker needed) --
used by tests, not meant to be set in normal deployments.
"""
from __future__ import annotations

from celery import Celery

from prometheus.config import settings

celery_app = Celery(
    "prometheus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["prometheus.tasks.document_tasks", "prometheus.tasks.web_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)
