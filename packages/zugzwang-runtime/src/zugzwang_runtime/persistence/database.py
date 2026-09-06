"""SQLite database bootstrap and connection management (design §11.3).

WAL mode, foreign keys, busy timeout. WAL is only enabled when the effectively
linked SQLite version sits in an approved corrected release line (shared policy,
ADR-044 as amended by ADR-CB-020 / TEST-081). The ``ephemeral`` policy profile
is an explicit non-durable mode (journal DELETE) for throwaway fixtures and
tests; it never backs a durable workspace (G-CB-04 pending).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from zugzwang_core.domain.errors import PersistenceError

from .sqlite_policy import WalPolicy, admitted, effective_version, wal_reason


class Database:
    """Owns the engine lifecycle for one workspace database."""

    def __init__(self, path: Path, wal_policy: WalPolicy = "enforce") -> None:
        self._path = path
        self._wal_policy: WalPolicy = wal_policy
        self._engine: Engine | None = None

    def open(self) -> Engine:
        if self._engine is not None:
            return self._engine
        self._assert_wal_policy()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{self._path}",
            future=True,
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(  # pyright: ignore[reportUnusedFunction]
            dbapi_connection: sqlite3.Connection, connection_record: Any
        ) -> None:
            cursor = dbapi_connection.cursor()
            if self._wal_policy == "ephemeral":
                cursor.execute("PRAGMA journal_mode=DELETE")
                cursor.execute("PRAGMA synchronous=OFF")
            else:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        self._engine = engine
        return engine

    def engine(self) -> Engine:
        if self._engine is None:
            return self.open()
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def _assert_wal_policy(self) -> None:
        """Fail closed before any connection when WAL is not admissible.

        In-memory databases do not use a WAL file, so the WAL-reset bug does
        not apply to them (PRD §25.1: schema validation is not operational
        validation). File-backed workspaces under ``enforce`` require an
        approved corrected release line.
        """
        if self._wal_policy != "enforce" or str(self._path) == ":memory:":
            return
        version = effective_version()
        if not admitted(version):
            raise PersistenceError(
                wal_reason(version),
                technical_context=str(self._path),
            )

    @property
    def path(self) -> Path:
        return self._path
