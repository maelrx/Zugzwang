"""Filesystem content-addressed store (design §11.7 and §10.5).

Commit protocol: serialize to temp → hash during write → fsync → atomic
rename into the CAS path → SQL transaction registers the artifact. A crash
between rename and SQL can only create an orphan (GC-safe); it can never
create a dangling reference (NFR-003).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from zugzwang_core.domain.artifacts import ArtifactPayload, ArtifactRef
from zugzwang_core.domain.canonical import sha256_hex
from zugzwang_core.domain.errors import ArtifactError, PersistenceError

from ..execution.artifacts import ArtifactStore


class ContentAddressedStore:
    """SHA-256 CAS over a local filesystem with sharded paths."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        payload: ArtifactPayload,
        *,
        compression: str | None = None,
        redaction_policy: str | None = None,
    ) -> ArtifactRef:
        ref = payload.ref(compression=compression, redaction_policy=redaction_policy)
        target = self._path_for(ref)
        if target.exists():
            return ref
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", suffix=".cas")
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload.data)
                handle.flush()
                os.fsync(handle.fileno())
            digest = sha256_hex(payload.data)
            if digest != ref.digest:
                raise ArtifactError(f"hash mismatch while writing artifact {ref.as_id()}")
            os.replace(tmp_path, target)
            tmp_path = None
        except OSError as exc:
            raise PersistenceError(
                f"failed to write artifact {ref.as_id()}",
                technical_context=str(exc),
            ) from exc
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        return ref

    def get(self, ref: ArtifactRef) -> ArtifactPayload:
        path = self._path_for(ref)
        if not path.exists():
            raise ArtifactError(f"artifact {ref.as_id()} not found in CAS")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PersistenceError(
                f"failed to read artifact {ref.as_id()}", technical_context=str(exc)
            ) from exc
        digest = sha256_hex(data)
        if digest != ref.digest:
            raise ArtifactError(
                f"artifact {ref.as_id()} failed integrity check (found {digest[:12]}...)"
            )
        return ArtifactPayload(media_type=ref.media_type, data=data)

    def exists(self, ref: ArtifactRef) -> bool:
        return self._path_for(ref).exists()

    def path_for(self, ref: ArtifactRef) -> Path:
        return self._path_for(ref)

    def delete(self, ref: ArtifactRef) -> None:
        path = self._path_for(ref)
        path.unlink(missing_ok=True)
        parent = path.parent
        if parent != self._root and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)

    def walk(self) -> list[ArtifactRef]:
        refs: list[ArtifactRef] = []
        for path in sorted(self._root.rglob("*")):
            if path.is_file() and path.name != ".tmp-*":
                digest = path.parent.name + path.name
                if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
                    refs.append(ArtifactRef(digest=digest, media_type="application/octet-stream"))
        return refs

    def _path_for(self, ref: ArtifactRef) -> Path:
        return self._root / ref.storage_path()

    @property
    def root(self) -> Path:
        return self._root


class FaultyArtifactStore:
    """Fault-injection wrapper: fails at configured operation offsets (design §24.2)."""

    def __init__(self, inner: ArtifactStore, fail_puts_at: set[int] | None = None) -> None:
        self._inner = inner
        self._fail_puts_at = fail_puts_at or set()
        self._puts = 0

    def put(
        self,
        payload: ArtifactPayload,
        *,
        compression: str | None = None,
        redaction_policy: str | None = None,
    ) -> ArtifactRef:
        self._puts += 1
        if self._puts in self._fail_puts_at:
            raise PersistenceError(f"injected artifact put failure at offset {self._puts}")
        return self._inner.put(payload, compression=compression, redaction_policy=redaction_policy)

    def get(self, ref: ArtifactRef) -> ArtifactPayload:
        return self._inner.get(ref)
