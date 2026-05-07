"""Object storage for downloadable artefacts.

A tiny abstraction so production runs against S3-compatible
(Cloudflare R2 / MinIO / AWS S3) and tests + local dev run against the
filesystem with no extra services.

The Protocol is async-friendly. Implementations:

  - ``LocalStorage(root)`` — writes under ``root/<key>``; ``url_for(key)``
    returns a ``file://`` URL plus a relative path.
  - ``S3Storage(...)`` — added later when we wire R2 credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class StorageObject:
    key: str
    url: str
    size_bytes: int


class Storage(Protocol):
    async def put(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> StorageObject: ...

    async def get(self, key: str) -> bytes: ...

    async def url_for(self, key: str, *, expires_seconds: int = 3600) -> str: ...


class LocalStorage:
    """Disk-backed Storage. Used in tests and the local CLI demo.

    ``url_for`` returns a ``file://`` URL so the CLI can print a click-able
    path; in production we'll swap in a presigned-URL provider that returns
    HTTPS.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Disallow escaping the root; keys are user-controlled.
        candidate = (self._root / key).resolve()
        if not str(candidate).startswith(str(self._root)):
            raise ValueError(f"key {key!r} escapes storage root")
        return candidate

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StorageObject:
        del content_type  # not stored on disk
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StorageObject(
            key=key,
            url=path.as_uri(),
            size_bytes=len(data),
        )

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def url_for(self, key: str, *, expires_seconds: int = 3600) -> str:
        del expires_seconds  # local: URLs don't expire
        return self._path(key).as_uri()


_default_storage: Storage | None = None


def get_storage() -> Storage:
    """Return the process-level Storage. Defaults to ``./out/artefacts``."""
    global _default_storage
    if _default_storage is None:
        _default_storage = LocalStorage(Path("out") / "artefacts")
    return _default_storage


def set_storage(storage: Storage | None) -> None:
    """Override the default. ``None`` resets to the default LocalStorage."""
    global _default_storage
    _default_storage = storage
