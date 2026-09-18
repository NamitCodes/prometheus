"""Local filesystem implementation of ObjectStorageProvider (MVP; see
new-plan.md section 33 -- object storage can be swapped in behind the same
interface later without touching callers)."""
from __future__ import annotations

import shutil
from pathlib import Path


class StorageKeyError(ValueError):
    """Raised when a storage key would resolve outside the storage root."""


class LocalObjectStorageProvider:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Path traversal protection (new-plan.md section 57): the resolved
        # path must stay under the storage root.
        resolved = (self._base_dir / key).resolve()
        if resolved != self._base_dir and self._base_dir not in resolved.parents:
            raise StorageKeyError(f"storage key escapes storage root: {key!r}")
        return resolved

    def save(self, source_path: Path, key: str) -> None:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, dest)

    def delete(self, key: str) -> None:
        dest = self._resolve(key)
        dest.unlink(missing_ok=True)
        # Prune now-empty parent directories up to (not including) the storage root.
        parent = dest.parent
        while parent != self._base_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def abs_path(self, key: str) -> Path:
        return self._resolve(key)

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
