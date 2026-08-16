"""Artifact store ports and implementations.

M0: in-memory store (vertical slice). M1: filesystem CAS with the commit
protocol of design §10.5. The interface is the same; only the adapter
changes. All operations are synchronous: local content-addressing needs no
async I/O, and the M1 single-writer serializes persistence separately.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from zugzwang_core.domain.artifacts import ArtifactPayload, ArtifactRef
from zugzwang_core.domain.errors import ArtifactError


@runtime_checkable
class ArtifactStore(Protocol):
    def put(
        self,
        payload: ArtifactPayload,
        *,
        compression: str | None = None,
        redaction_policy: str | None = None,
    ) -> ArtifactRef: ...

    def get(self, ref: ArtifactRef) -> ArtifactPayload: ...


class InMemoryArtifactStore:
    """Content-addressed in-memory store with natural deduplication."""

    def __init__(self) -> None:
        self._objects: dict[str, ArtifactPayload] = {}

    def put(
        self,
        payload: ArtifactPayload,
        *,
        compression: str | None = None,
        redaction_policy: str | None = None,
    ) -> ArtifactRef:
        ref = payload.ref(compression=compression, redaction_policy=redaction_policy)
        self._objects.setdefault(ref.digest, payload)
        return ref

    def get(self, ref: ArtifactRef) -> ArtifactPayload:
        payload = self._objects.get(ref.digest)
        if payload is None:
            raise ArtifactError(f"artifact {ref.as_id()} not found")
        return payload

    def __len__(self) -> int:
        return len(self._objects)
