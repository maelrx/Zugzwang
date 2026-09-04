"""Fresh and forward migration checks for the research projections."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager


@pytest.mark.compatibility
def test_research_migrations_upgrade_from_0002_and_fresh_db(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.db")
    engine = database.open()
    schema = SchemaManager(engine)
    schema.upgrade()
    assert schema.current_revision() == "0006"

    inspector = inspect(engine)
    assert {"evaluation_runs", "search_sessions", "search_nodes", "search_edges"}.issubset(
        inspector.get_table_names()
    )
    assert "decision_trace_artifact_id" in {
        column["name"] for column in inspector.get_columns("steps")
    }

    config = Config()
    from zugzwang_runtime import migration_dir

    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.path}")
    command.downgrade(config, "0002")
    assert schema.current_revision() == "0002"

    schema.upgrade()
    assert schema.current_revision() == "0006"
    inspector = inspect(engine)
    assert "reasoning_telemetry_artifact_id" in {
        column["name"] for column in inspector.get_columns("attempts")
    }
