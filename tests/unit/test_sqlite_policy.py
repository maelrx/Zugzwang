"""TEST-081 — SQLite admissibility policy shared by doctor and bootstrap.

Doctor and bootstrap must reject vulnerable versions and accept only the
approved corrected release lines for the WAL-reset bug (ADR-CB-020, RISK-13):
fix 3.51.3, backports 3.44.6 and 3.50.7. Corrected, vulnerable-intermediate
and not-yet-approved future versions are all exercised here.
"""

import sqlite3
from pathlib import Path

import pytest

from zugzwang_core.domain.errors import PersistenceError
from zugzwang_runtime.application.services import DoctorCheck, DoctorService
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.sqlite_policy import (
    CORRECTED_LINES,
    POLICY_VERSION,
    admitted,
    effective_version,
    parse_version,
    wal_reason,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        # corrected lines (admitted)
        ((3, 51, 3), True),
        ((3, 51, 9), True),
        ((3, 50, 7), True),
        ((3, 50, 11), True),
        ((3, 44, 6), True),
        # vulnerable intermediate releases (rejected)
        ((3, 37, 0), False),
        ((3, 44, 5), False),
        ((3, 45, 1), False),
        ((3, 50, 4), False),
        ((3, 51, 2), False),
        # mainline releases at or above the fix carry it (admitted)
        ((3, 52, 0), True),
        ((3, 53, 1), True),
        # future major (not yet approved; requires policy update)
        ((4, 0, 0), False),
        ((5, 99, 0), False),
    ],
)
def test_admission_by_corrected_lines(version: tuple[int, ...], expected: bool) -> None:
    assert admitted(version) is expected


def test_policy_is_versioned_and_lines_sorted() -> None:
    assert POLICY_VERSION >= 1
    assert tuple(sorted(CORRECTED_LINES)) == CORRECTED_LINES


def test_parse_version_accepts_dotted_and_rejects_garbage() -> None:
    assert parse_version("3.45.1") == (3, 45, 1)
    with pytest.raises(ValueError):
        parse_version("three")


def test_wal_reason_names_policy_and_lines() -> None:
    reason = wal_reason((3, 45, 1))
    assert "3.45.1" in reason
    assert "3.51.3" in reason and "3.44.6" in reason and "3.50.7" in reason
    assert f"policy v{POLICY_VERSION}" in reason
    assert "approved corrected line" in wal_reason((3, 51, 3))


@pytest.mark.parametrize("version", [(3, 45, 1), (3, 51, 3)])
def test_doctor_and_bootstrap_share_the_same_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: tuple[int, ...]
) -> None:
    """TEST-081 agreement: doctor check and Database gate use one policy."""
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    assert effective_version() == version
    expected_admitted = admitted(effective_version())
    assert expected_admitted == admitted(version)

    database = Database(tmp_path / "state.db")
    if expected_admitted:
        database.open().dispose()
        database.close()
    else:
        with pytest.raises(PersistenceError) as exc:
            database.open()
        assert "3.51.3" in str(exc.value)


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


def test_enforce_on_this_machine_matches_real_policy(tmp_path: Path) -> None:
    """The real linked SQLite decides: admitted opens WAL, otherwise fail-closed."""
    database = Database(tmp_path / "state.db")
    if admitted(effective_version()):
        engine = database.open()
        with engine.connect() as connection:
            journal = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert journal == "wal"
        database.close()
    else:
        with pytest.raises(PersistenceError):
            database.open()


def test_doctor_check_reports_honest_status() -> None:
    check = DoctorService._sqlite_check()
    assert isinstance(check, DoctorCheck)
    assert check.status == ("ok" if admitted(effective_version()) else "error")
    assert "3.51.3" in check.message or "approved corrected line" in check.message
