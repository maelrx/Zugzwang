"""Canonical JSON and content hashing.

The canonical form is: UTF-8, sorted keys, no insignificant whitespace, fixed
number formatting, UTC timestamps with ``Z`` suffix. Two semantically equal
values always hash identically; key order in input never matters.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from .clocks import to_iso_z

_HASH_ALGORITHMS = {"sha256": hashlib.sha256}


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize ``value`` to canonical JSON bytes (sorted keys, compact)."""
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_string(value: Any) -> str:
    """Canonical JSON as a string (for display/debug only)."""
    return canonical_json_bytes(value).decode("utf-8")


def _normalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("canonical JSON cannot represent NaN or infinity")
        return float(repr(value))
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        return to_iso_z(value)
    if isinstance(value, dict):
        raw: dict[Any, Any] = cast(dict[Any, Any], value)
        pairs: list[tuple[str, Any]] = [(str(key), _normalize(raw[key])) for key in raw]
        pairs.sort(key=lambda pair: pair[0])
        return dict(pairs)
    if isinstance(value, (list, tuple)):
        raw_list: list[Any] = cast(list[Any], value)
        return [_normalize(v) for v in raw_list]
    if isinstance(value, (set, frozenset)):
        raw_set: list[Any] = list(cast(set[Any], value))
        return [_normalize(v) for v in sorted(raw_set, key=repr)]
    dumper = getattr(value, "model_dump", None)
    if callable(dumper):
        return _normalize(dumper(mode="json"))
    if hasattr(value, "__dict__"):
        raise TypeError(f"cannot canonicalize arbitrary object {type(value).__name__}: {value!r}")
    raise TypeError(f"cannot canonicalize value of type {type(value).__name__}")


def sha256_bytes(data: bytes) -> bytes:
    """SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """SHA-256 digest of raw bytes, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def hash_canonical(value: Any) -> str:
    """SHA-256 hex of the canonical JSON form of ``value``."""
    return sha256_hex(canonical_json_bytes(value))


@dataclass(frozen=True, slots=True)
class ContentHash:
    """A verified content hash."""

    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm not in _HASH_ALGORITHMS:
            raise ValueError(f"unsupported hash algorithm {self.algorithm!r}")
        digest_length = _HASH_ALGORITHMS[self.algorithm]().digest_size * 2
        if len(self.digest) != digest_length or any(
            c not in "0123456789abcdefABCDEF" for c in self.digest
        ):
            raise ValueError(f"invalid {self.algorithm} digest {self.digest!r}")

    @classmethod
    def of_bytes(cls, data: bytes, algorithm: str = "sha256") -> ContentHash:
        hasher = _HASH_ALGORITHMS[algorithm]()
        hasher.update(data)
        return cls(algorithm=algorithm, digest=hasher.hexdigest())

    @classmethod
    def of_canonical(cls, value: Any, algorithm: str = "sha256") -> ContentHash:
        return cls.of_bytes(canonical_json_bytes(value), algorithm)

    def hex(self) -> str:
        return self.digest.lower()

    def __str__(self) -> str:
        return f"{self.algorithm}:{self.hex()}"
