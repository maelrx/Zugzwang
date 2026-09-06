"""TEST-081 — SQLite admissibility policy shared by doctor and bootstrap.

Doctor and bootstrap must reject vulnerable versions and accept only the
approved corrected release lines for the WAL-reset bug (ADR-CB-020, RISK-13):
mainline fix 3.51.3 (and later 3.x), backports 3.44.6 and 3.50.7. Corrected,
vulnerable-intermediate and not-yet-approved future versions are all exercised
here through a monkeypatched linked version, so the suite is deterministic on
any machine (TEST_STRATEGY §4).
"""

import sqlite3
from pathlib import Path

import pytest

from zugzwang_core.domain.errors import PersistenceError
from zugzwang_runtime.application.services import DoctorCheck, DoctorService
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.sqlite_policy import (
    CORRECTED_LINES,
    MAINLINE_FIX,
    NEXT_MAJOR,
    POLICY_VERSION,
    effective_version,
    wal_reason,
    wal_safe,
)
from zugzwang_runtime.workspace import Workspace

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        # corrected lines (admitted)
        ((3, 51, 3), True),
        ((3, 51, 9), True),
        ((3, 53, 1), True),
        ((3, 50, 7), True),
        ((3, 50, 11), True),
        ((3, 44, 6), True),
        # vulnerable intermediate releases (rejected)
        ((3, 37, 0), False),
        ((3, 44, 5), False),
        ((3, 45, 1), False),
        ((3, 50, 4), False),
        ((3, 51, 2), False),
        # unproven future major (rejected until policy update with evidence)
        ((4, 0, 0), False),
        ((5, 99, 0), False),
    ],
)
def test_admission_by_corrected_lines(version: tuple[int, ...], expected: bool) -> None:
    assert wal_safe(version) is expected


def test_policy_is_versioned_and_lines_sorted() -> None:
    assert POLICY_VERSION >= 2
    assert tuple(sorted(CORRECTED_LINES)) == CORRECTED_LINES
    assert MAINLINE_FIX < NEXT_MAJOR


def test_wal_reason_names_policy_lines_and_remediation() -> None:
    reason = wal_reason((3, 45, 1))
    assert "3.45.1" in reason
    assert "3.51.3" in reason and "3.44.6" in reason and "3.50.7" in reason
    assert f"policy v{POLICY_VERSION}" in reason
    assert "ZUGZWANG_WAL_POLICY" in reason and "no external work accepted" in reason
    assert "approved corrected line" in wal_reason((3, 51, 3))


@pytest.mark.parametrize("version", [(3, 45, 1), (3, 51, 3)])
def test_doctor_and_bootstrap_share_the_same_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: tuple[int, ...]
) -> None:
    """TEST-081 agreement: doctor check and Database gate use one policy."""
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    assert effective_version() == version
    expected = wal_safe(version)

    database = Database(tmp_path / "state.db")
    if expected:
        database.open().dispose()
        database.close()
    else:
        with pytest.raises(PersistenceError) as exc:
            database.open()
        assert "3.51.3" in str(exc.value)

    check = DoctorService._sqlite_check()
    assert isinstance(check, DoctorCheck)
    assert (check.status == "ok") is expected
    assert ("NOT in an approved" in check.message) is (not expected)


def test_ephemeral_profile_opens_on_vulnerable_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The explicit non-durable profile never fails closed and never uses WAL."""
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 45, 1))
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    with engine.connect() as connection:
        journal = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        synchronous = connection.exec_driver_sql("PRAGMA synchronous").scalar()
    assert journal == "delete"
    assert synchronous == 0  # synchronous=OFF
    database.close()


def test_storage_check_reports_error_on_policy_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fail-closed policy rejection is an error check, not a warn downgrade."""
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 45, 1))
    workspace = Workspace.from_root(tmp_path, wal_policy="enforce")
    checks = DoctorService._storage_checks(workspace)
    db_checks = [c for c in checks if c.check == "db"]
    assert db_checks, "storage check must always report"
    assert db_checks[0].status == "error"
    assert "NOT in an approved" in db_checks[0].message
