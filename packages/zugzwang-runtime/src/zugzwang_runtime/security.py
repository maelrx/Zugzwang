"""Redaction policies (design §20.7) and secret references (FR-049).

Secrets never enter events, resolved manifests or bundles. ``env:``
references are resolved in-memory at the adapter boundary only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, cast

from zugzwang_core.domain.canonical import sha256_hex
from zugzwang_core.domain.errors import SecurityError

REDACTION_POLICIES = ("none", "standard", "strict")


@dataclass(frozen=True, slots=True)
class SecretRef:
    """A reference to a secret by source (never the value)."""

    source: str
    key: str

    @classmethod
    def parse(cls, value: str) -> SecretRef:
        if value.startswith("env:"):
            key = value[len("env:") :]
            if not key:
                raise SecurityError("empty env secret reference")
            return cls(source="env", key=key)
        raise SecurityError(
            "credentials must be references (env:VAR), got a literal",
        )

    def resolve(self) -> str:
        if self.source == "env":
            value = os.environ.get(self.key)
            if value is None:
                raise SecurityError(
                    f"environment variable {self.key} is not set",
                    technical_context="secret referenced but not available",
                )
            return value
        raise SecurityError(f"unknown secret source {self.source!r}")

    def __str__(self) -> str:
        return f"{self.source}:{self.key}"


def resolve_secret(value: str | None) -> str | None:
    """Resolve an env: reference (or None). Literals are rejected."""
    if value is None or value == "":
        return None
    if value.startswith("env:"):
        return SecretRef.parse(value).resolve()
    raise SecurityError(
        "credentials must be env: references; literal secrets are forbidden in manifests"
    )


def apply_redaction(policy: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply a redaction policy to a payload before persistence.

    ``none`` keeps everything (non-sensitive content only); ``standard``
    strips credential-shaped fields; ``strict`` also hashes prompt text so
    the content is not retained (replayability is declared in the bundle).
    """
    if policy not in REDACTION_POLICIES:
        raise SecurityError(f"unknown redaction policy {policy!r}")
    if policy == "none":
        return payload
    redacted = _redact(payload, hash_text=policy == "strict")
    return cast_dict(redacted)


_CREDENTIAL_KEYS = {"api_key", "apikey", "authorization", "secret", "token", "password"}

RedactedValue = Any


def _redact(value: Any, *, hash_text: bool) -> RedactedValue:
    if isinstance(value, dict):
        raw: dict[Any, Any] = dict(cast(dict[Any, Any], value))
        result: dict[str, Any] = {}
        for key, item in raw.items():
            if str(key).lower().replace("-", "_") in _CREDENTIAL_KEYS:
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = _redact(item, hash_text=hash_text)
        return result
    if isinstance(value, list):
        raw_list: list[Any] = list(cast(list[Any], value))
        return [_redact(item, hash_text=hash_text) for item in raw_list]
    if hash_text and isinstance(value, str) and len(value) > 8:
        return f"sha256:{sha256_hex(value.encode('utf-8'))[:16]}"
    return value


def cast_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SecurityError("redaction produced a non-object payload")
    return cast(dict[str, Any], value)
