"""Artifact identity (design §11.7).

Artifacts are immutable, content-addressed blobs. Metadata that can change
lives in the database, never in the object. The canonical identity is
``sha256:<hex>`` with a mandatory media type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .canonical import ContentHash
from .errors import ArtifactError

_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A verified reference to a content-addressed artifact."""

    algorithm: Literal["sha256"] = "sha256"
    digest: str = ""
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None
    compression: str | None = None
    redaction_policy: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.digest):
            raise ValueError(f"invalid sha256 digest {self.digest!r}")
        if not self.media_type or "/" not in self.media_type:
            raise ValueError(f"invalid media type {self.media_type!r}")

    @classmethod
    def of_bytes(
        cls,
        data: bytes,
        media_type: str,
        *,
        compression: str | None = None,
        redaction_policy: str | None = None,
    ) -> ArtifactRef:
        return cls(
            digest=ContentHash.of_bytes(data).hex(),
            media_type=media_type,
            size_bytes=len(data),
            compression=compression,
            redaction_policy=redaction_policy,
        )

    @classmethod
    def parse(cls, value: str) -> ArtifactRef:
        match = _DIGEST_RE.fullmatch(value)
        if not match:
            raise ArtifactError(f"invalid artifact reference {value!r}")
        return cls(digest=match.group(1))

    def as_id(self) -> str:
        return f"{self.algorithm}:{self.digest.lower()}"

    def storage_path(self) -> str:
        """CAS sharded relative path: ``ab/cdef...``."""
        digest = self.digest.lower()
        return f"{digest[:2]}/{digest[2:]}"

    def __str__(self) -> str:
        return self.as_id()


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    """Serialized artifact content plus its media type (bytes stay in memory)."""

    media_type: str
    data: bytes

    def __post_init__(self) -> None:
        if not self.media_type or "/" not in self.media_type:
            raise ValueError(f"invalid media type {self.media_type!r}")

    def ref(
        self, *, compression: str | None = None, redaction_policy: str | None = None
    ) -> ArtifactRef:
        return ArtifactRef.of_bytes(
            self.data,
            self.media_type,
            compression=compression,
            redaction_policy=redaction_policy,
        )
