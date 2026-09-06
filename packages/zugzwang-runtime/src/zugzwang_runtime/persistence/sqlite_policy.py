"""Versioned SQLite admissibility policy shared by doctor and bootstrap (TEST-081).

ADR-044 requires WAL-safe SQLite; the WAL-reset corruption bug affects every
release from 3.7.0 through 3.51.2 and was fixed in 3.51.3 with backports to
3.44.6 and 3.50.7 (sqlite.org/wal.html, sqlite.org/news.html, 2026-03). A naive
floor (``>=3.44.6``) would admit vulnerable intermediate releases, so admission
is by corrected release line: a version is admitted only when it belongs to the
same maintenance branch as an approved fix and is at or above it.

Future/unapproved lines are rejected until this table is updated with new
release evidence (ADR-CB-020). The durable profile (fsync/``synchronous=FULL``)
is a separate decision (G-CB-04, pending) and is intentionally absent here.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

POLICY_VERSION = 2

# Approved corrected lines for the WAL-reset bug. The mainline fix is 3.51.3
# (2026-03-13); every 3.x release at or above it carries the fix. The
# maintenance-branch backports are 3.44.6 and 3.50.7 — a version is admitted
# when it belongs to a backported branch and is at or above its fix, or when
# it is at or above the mainline fix within the 3.x series. Releases from a
# future major (4.x) are rejected until this policy is updated with release
# evidence (ADR-CB-020: update on new evidence, never assume).
CORRECTED_LINES: tuple[tuple[int, int, int], ...] = (
    (3, 44, 6),
    (3, 50, 7),
    (3, 51, 3),
)
MAINLINE_FIX: tuple[int, ...] = (3, 51, 3)
NEXT_MAJOR: tuple[int, ...] = (4, 0, 0)

WalPolicy = Literal["enforce", "ephemeral"]


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted version string deterministically (accepts 3/4 parts)."""
    parts = tuple(int(p) for p in version.split("."))
    if len(parts) < 3 or any(p < 0 for p in parts):
        raise ValueError(f"unparseable sqlite version: {version!r}")
    return parts


def admitted(version: tuple[int, ...]) -> bool:
    """True when `version` sits in an approved corrected release line."""
    if MAINLINE_FIX <= version < NEXT_MAJOR:
        return True
    return any(version[:2] == line[:2] and version >= line for line in CORRECTED_LINES)


def effective_version() -> tuple[int, ...]:
    """The SQLite version actually linked into this Python process."""
    return tuple(sqlite3.sqlite_version_info)


def wal_reason(version: tuple[int, ...]) -> str:
    """Human explanation of the admission decision for `version`."""
    approved = ", ".join(".".join(str(p) for p in line) for line in CORRECTED_LINES)
    if admitted(version):
        shown = ".".join(str(p) for p in version)
        return f"sqlite {shown} is in an approved corrected line ({approved})"
    shown = ".".join(str(p) for p in version)
    return (
        f"sqlite {shown} is NOT in an approved corrected line for WAL "
        f"(WAL-reset bug affects 3.7.0-3.51.2; mainline fix 3.51.3; backports "
        f"3.44.6/3.50.7; policy v{POLICY_VERSION} approves 3.x >= 3.51.3 plus "
        f"backported branches {approved}) — upgrade sqlite or request a policy "
        f"update with release evidence"
    )
