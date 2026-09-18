"""Object storage provider interface (new-plan.md section 33).

Keeps the rest of the app (services, CLI) ignorant of *how* uploaded files
are stored -- local disk today, S3-compatible storage later, without
touching callers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ObjectStorageProvider(Protocol):
    def save(self, source_path: Path, key: str) -> None:
        """Copy the file at `source_path` into storage under `key`."""
        ...

    def delete(self, key: str) -> None:
        """Remove the stored file at `key`, if it exists."""
        ...

    def abs_path(self, key: str) -> Path:
        """Resolve `key` to an absolute filesystem path for reading."""
        ...

    def exists(self, key: str) -> bool: ...
