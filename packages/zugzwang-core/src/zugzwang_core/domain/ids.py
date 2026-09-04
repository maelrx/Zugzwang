"""Entity identifiers.

IDs are opaque strings with a stable type prefix (``run_``, ``ep_``, ...) and a
random body. IDs never encode scheduling order; determinism lives in seeds
(see :mod:`zugzwang_core.domain.seeds`), never in identity.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Final, Literal

_ID_RE = re.compile(r"^[a-z]{2,4}_[A-Za-z0-9_-]{22}$")

_IdPrefix = Literal[
    "exp",
    "cnd",
    "run",
    "ep",
    "stp",
    "att",
    "evt",
    "art",
    "bun",
    "evl",
    "eval",
    "ses",
]


@dataclass(frozen=True, slots=True)
class Id:
    """A validated opaque identifier with a domain prefix."""

    value: str

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.value):
            raise ValueError(f"invalid id {self.value!r}: expected '<prefix>_<22 url-safe chars>'")

    @property
    def prefix(self) -> str:
        return self.value.split("_", 1)[0]

    def __str__(self) -> str:
        return self.value


def new_id(prefix: _IdPrefix) -> Id:
    """Create a fresh random identifier with the given prefix."""
    return Id(f"{prefix}_{secrets.token_urlsafe(16)}")


PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "exp",
        "cnd",
        "run",
        "ep",
        "stp",
        "att",
        "evt",
        "art",
        "bun",
        "evl",
        "eval",
        "ses",
    }
)
