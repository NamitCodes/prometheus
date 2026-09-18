"""Object storage provider factory."""
from __future__ import annotations

from prometheus.config import settings
from prometheus.providers.storage.base import ObjectStorageProvider
from prometheus.providers.storage.local import LocalObjectStorageProvider

_provider: ObjectStorageProvider | None = None


def get_storage_provider() -> ObjectStorageProvider:
    global _provider
    if _provider is None:
        _provider = LocalObjectStorageProvider(settings.document_storage_dir)
    return _provider
