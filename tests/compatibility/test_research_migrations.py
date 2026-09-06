"""Fresh and forward migration checks for the research projections."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import (
    EpisodeRepository,
    EventRepository,
    SchemaManager,
    StepRepository,
)


@pytest.mark.compatibility
def test_research_migrations_upgrade_from_0002_and_fresh_db(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
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


@pytest.mark.compatibility
def test_legacy_metrics_remain_visible_and_separate_after_0003_upgrade(
    tmp_path: Path,
) -> None:
    """ZGW-0085/#13 item 3: pre-0003 metrics (no evaluation_run_id) survive the
    upgrade, stay visible in reports as an identified legacy group, and are not
    mixed with newer evaluation generations."""
    import sqlalchemy as sa

    from zugzwang_runtime.application.evaluation import ReportRunService
    from zugzwang_runtime.persistence.repositories import (
        EvaluationRunRepository,
        MetricObservationRepository,
        RunRepository,
    )

    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    schema = SchemaManager(engine)
    schema.upgrade()
    run_id = "run_legacymetrics"
    RunRepository(engine).insert_run(
        {
            "run_id": run_id,
            "condition_id": "cond-legacy",
            "status": "COMPLETED",
            "protocol_hash": "0" * 64,
            "declared_assistance": "H2",
            "projection_version": 1,
        }
    )

    # Rewind to the pre-0003 schema and record a metric the old way: the table
    # has no evaluation_run_id column at that revision.
    config = Config()
    from zugzwang_runtime import migration_dir

    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.path}")
    command.downgrade(config, "0002")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO metric_observations (metric_observation_id, run_id, "
                "metric_definition_id, metric_version, value_num, unit, "
                "dimensions_json, evaluator_id, evaluator_version) "
                "VALUES (:id, :run_id, :metric, :version, :value, :unit, '{}', "
                "'legacy.evaluator', '0.0.0')"
            ),
            {
                "id": "evl_legacy000",
                "run_id": run_id,
                "metric": "chess.cpl",
                "version": "1.0.0",
                "value": 42.0,
                "unit": "cp",
            },
        )

    schema.upgrade()
    assert schema.current_revision() == "0006"

    # A newer generation with full provenance must not be mixed with the
    # legacy record.
    evaluation_run_id = "eval_newgen001"
    EvaluationRunRepository(engine).insert(
        {
            "evaluation_run_id": evaluation_run_id,
            "source_run_id": run_id,
            "evaluator_id": "stockfish",
            "evaluator_version": "1.0.0",
            "engine_json": {},
            "config_json": {},
            "status": "COMPLETED",
            "created_at": "2026-09-05T00:00:00Z",
        }
    )
    MetricObservationRepository(engine).insert(
        {
            "metric_observation_id": "evl_newgen0001",
            "run_id": run_id,
            "evaluation_run_id": evaluation_run_id,
            "metric_definition_id": "chess.cpl",
            "metric_version": "1.0.0",
            "value_num": 7.0,
            "unit": "cp",
            "dimensions_json": {},
            "evaluator_id": "stockfish",
            "evaluator_version": "1.0.0",
        }
    )

    report = ReportRunService(
        runs=RunRepository(engine),
        episodes=EpisodeRepository(engine),
        steps=StepRepository(engine),
        metrics=MetricObservationRepository(engine),
        events=EventRepository(engine),
        evaluation_runs=EvaluationRunRepository(engine),
    ).report(run_id)

    legacy = report["legacy_metrics"]
    assert [row["metric_observation_id"] for row in legacy["observations"]] == ["evl_legacy000"]
    assert "unknown" in legacy["note"]
    assert [row["metric_observation_id"] for row in report["metrics"]] == ["evl_newgen0001"]

    markdown = ReportRunService(
        runs=RunRepository(engine),
        episodes=EpisodeRepository(engine),
        steps=StepRepository(engine),
        metrics=MetricObservationRepository(engine),
        events=EventRepository(engine),
        evaluation_runs=EvaluationRunRepository(engine),
    ).to_markdown(report)
    assert "## Legacy metrics" in markdown
    assert "chess.cpl@1.0.0" in markdown
    assert "42.0" in markdown
    # The legacy value must not leak into the identified generation section.
    assert markdown.index("## Metrics") < markdown.index("## Legacy metrics")
