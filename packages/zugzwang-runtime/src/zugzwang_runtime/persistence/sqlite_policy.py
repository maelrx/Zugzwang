"""Versioned SQLite admissibility policy shared by doctor and bootstrap (TEST-081).

ADR-044 requires WAL-safe SQLite. The WAL-reset corruption bug affects every
release from 3.7.0 through 3.51.2 and was fixed in 3.51.3 with backports to
3.44.6 and 3.50.7; per sqlite.org/wal.html the bug "is fixed in version 3.51.3
(2026-03-13) and later", so every 3.x release at or above the mainline fix
carries it. Admission therefore accepts: the 3.x mainline at or above 3.51.3,
and the backported branches at or above their fix patch. A naive floor
(``>=3.44.6``) would admit vulnerable intermediate releases. Vulnerable
intermediates and unproven future majors are rejected until this policy is
updated with release evidence (ADR-CB-020: update on new evidence, never
assume). The durable profile (fsync/``synchronous=FULL``) is a separate
decision (G-CB-04, pending) and is intentionally absent here.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

POLICY_VERSION = 2

# Approved corrected lines for the WAL-reset bug (branch, first fixed patch).
CORRECTED_LINES: tuple[tuple[int, int, int], ...] = (
    (3, 44, 6),
    (3, 50, 7),
    (3, 51, 3),
)
MAINLINE_FIX: tuple[int, ...] = (3, 51, 3)
NEXT_MAJOR: tuple[int, ...] = (4, 0, 0)

WalPolicy = Literal["enforce", "ephemeral"]


def effective_version() -> tuple[int, ...]:
    """The SQLite version actually linked into this Python process."""
    return tuple(sqlite3.sqlite_version_info)


def wal_safe(version: tuple[int, ...]) -> bool:
    """True when `version` may open WAL (sits in an approved corrected line)."""
    if MAINLINE_FIX <= version < NEXT_MAJOR:
        return True
    return any(version[:2] == line[:2] and version >= line for line in CORRECTED_LINES)


def wal_reason(version: tuple[int, ...]) -> str:
    """Full decision record: what, remediation, retryability and evidence."""
    shown = ".".join(str(p) for p in version)
    approved = ", ".join(".".join(str(p) for p in line) for line in CORRECTED_LINES)
    if wal_safe(version):
        return f"sqlite {shown} is in an approved corrected line ({approved})"
    return (
        f"sqlite {shown} is NOT in an approved corrected line for WAL "
        f"(WAL-reset bug affects 3.7.0-3.51.2; mainline fix 3.51.3; backports "
        f"3.44.6/3.50.7; policy v{POLICY_VERSION} approves 3.x >= 3.51.3 plus "
        f"backported branches {approved}). remediation: upgrade the linked "
        f"sqlite (retryable after upgrade) or run explicitly non-durable with "
        f"ZUGZWANG_WAL_POLICY=ephemeral; no external work accepted; evidence: "
        f"policy v{POLICY_VERSION} per sqlite.org/wal.html and ADR-CB-020"
    )
