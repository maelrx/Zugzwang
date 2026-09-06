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
    assert schema.current_revision() == "0010"

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
    assert schema.current_revision() == "0010"
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
    assert schema.current_revision() == "0010"

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


@pytest.mark.compatibility
def test_migration_0009_freezes_bindings_and_round_trips(tmp_path: Path) -> None:
    """ZGW-0101: NULL->binding is refused after the decision freezes; the
    downgrade->upgrade round-trip is idempotent (columns, triggers)."""
    import sqlalchemy as sa

    database = Database(tmp_path / "state9.db", wal_policy="ephemeral")
    engine = database.open()
    schema = SchemaManager(engine)
    schema.upgrade()
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:9','sha256',1,"
                "'application/json','cb/9.json','2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
                "declared_assistance, projection_version, assistance_violated) "
                "VALUES ('run-9','cond-9','RUNNING','proto','H0',0,0)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
                "status, assistance_violated) VALUES ('ep-9','run-9',0,"
                "'chess.full_game',7,'RUNNING',0)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
                "assistance_violated) VALUES ('st-9','ep-9',0,'model:main','RUNNING',0)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-9','run-9','alg','0.1','ns',"
                "'node-9','{}','{}','RUNNING','2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO cb_state_snapshots (state_key, state_schema_version, "
                "rules_version, variant, position_key, history_completeness, "
                "state_artifact_id, created_at) SELECT 'state-9','state/v2',"
                "'standard/v1','standard','pos-9','complete','art:9',"
                "'2026-09-06T00:00:00Z' WHERE NOT EXISTS "
                "(SELECT 1 FROM cb_state_snapshots WHERE state_key = 'state-9')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO cb_memory_snapshots (snapshot_id, scope_kind, "
                "scope_owner_id, partition_name, status, policy_hash, "
                "manifest_artifact_id, sealed_at, created_at) "
                "VALUES ('snap-9','episode','ep-9','development','SEALED','p', "
                "'art:9','2026-09-06T00:00:00Z','2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO cb_decisions (decision_id, step_id, decision_ordinal, "
                "search_session_id, root_state_key, status, strategy_id, "
                "strategy_version, interaction_mode, policy_hash, config_artifact_id, "
                "created_at) SELECT 'dec-9','st-9',0,'sess-9', "
                " 'state-9', 'ACTIVE', 's','0','native_tools','p','art:9', "
                "'2026-09-06T00:00:00Z' FROM cb_state_snapshots ss LIMIT 1"
            )
        )
        conn.commit()

    def _try_bind() -> None:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE cb_decisions SET memory_snapshot_id = 'snap-9' "
                    "WHERE decision_id = 'dec-9'"
                )
            )

    # ACTIVE decision: the authorized phase — first binding succeeds.
    _try_bind()
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "UPDATE cb_decisions SET status = 'COMMITTED', "
                "selected_action = 'e2e4', selection_source = 'model' "
                "WHERE decision_id = 'dec-9'"
            )
        )
        conn.commit()

    # A second decision frozen WITHOUT a binding can no longer bind late.
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-9b','run-9','alg','0.1','ns',"
                "'node-9b','{}','{}','RUNNING','2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO cb_decisions (decision_id, step_id, decision_ordinal, "
                "search_session_id, root_state_key, status, strategy_id, "
                "strategy_version, interaction_mode, policy_hash, config_artifact_id, "
                "created_at) VALUES ('dec-9b','st-9',1,'sess-9b', "
                "'state-9', 'ACTIVE', 's','0','native_tools','p','art:9', "
                "'2026-09-06T00:00:00Z')"
            )
        )
        conn.commit()
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "UPDATE cb_decisions SET status = 'COMMITTED', selected_action = 'e2e4', "
                "selection_source = 'model' WHERE decision_id = 'dec-9b'"
            )
        )
        conn.commit()
    with pytest.raises(Exception, match="freeze|sealed|immutable"):
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE cb_decisions SET memory_snapshot_id = 'snap-9' "
                    "WHERE decision_id = 'dec-9b'"
                )
            )

    # Round-trip: downgrade (with data present) is refused BEFORE any DDL…
    config = Config()
    from zugzwang_runtime import migration_dir

    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.path}")
    with pytest.raises(RuntimeError, match="bound decision"):
        command.downgrade(config, "0008")
    # 0009's own downgrade refused BEFORE dropping anything: the skill tables
    # survive and the binding row is intact.
    assert schema.current_revision() == "0009"
    with engine.connect() as conn:
        assert (
            conn.execute(
                sa.text("SELECT memory_snapshot_id FROM cb_decisions WHERE decision_id = 'dec-9'")
            ).fetchone()[0]
            == "snap-9"
        )
        tables = set(inspect(engine).get_table_names())
        assert "cb_skill_versions" in tables

    # …and on a CLEAN schema the downgrade->upgrade round-trip is idempotent.
    clean = Database(tmp_path / "state9-clean.db", wal_policy="ephemeral")
    clean_engine = clean.open()
    SchemaManager(clean_engine).upgrade()
    clean_config = Config()
    clean_config.set_main_option("script_location", str(migration_dir))
    clean_config.set_main_option("sqlalchemy.url", f"sqlite:///{clean.path}")
    command.downgrade(clean_config, "0002")
    SchemaManager(clean_engine).upgrade()
    assert SchemaManager(clean_engine).current_revision() == "0010"
    columns = {c["name"] for c in inspect(clean_engine).get_columns("cb_decisions")}
    assert {"memory_snapshot_id", "skill_set_id"}.issubset(columns)
    with clean_engine.connect() as conn:
        triggers = {
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND tbl_name = 'cb_decisions'"
                )
            ).fetchall()
        }
    assert "cb_decision_late_binding" in triggers
