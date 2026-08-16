"""SQLite database bootstrap and connection management (design §11.3).

WAL mode, foreign keys, busy timeout. SQLite's minimum safe version for WAL
is enforced at open time (ADR-044).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from zugzwang_core.domain.errors import PersistenceError

MIN_SAFE_SQLITE = (3, 37, 0)


class Database:
    """Owns the engine lifecycle for one workspace database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._engine: Engine | None = None

    def open(self) -> Engine:
        if self._engine is not None:
            return self._engine
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
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        self._engine = engine
        self._check_sqlite_version()
        return engine

    def engine(self) -> Engine:
        if self._engine is None:
            return self.open()
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def _check_sqlite_version(self) -> None:
        connection = sqlite3.connect(self._path)
        try:
            version = connection.execute("SELECT sqlite_version()").fetchone()[0]
        finally:
            connection.close()
        parts = tuple(int(p) for p in str(version).split("."))
        if parts < MIN_SAFE_SQLITE:
            raise PersistenceError(
                f"sqlite {version} is below the minimum safe version for WAL (3.37.0 required)",
                technical_context=str(self._path),
            )

    @property
    def path(self) -> Path:
        return self._path
