"""CB-WO-04 acceptance — CB-M1 persistence and decision journal (PRD §38.5, §23).

Upgrade on a baseline copy, feature rollback, referential integrity, writer
idempotency, §12.2 status transitions, append-only budget journal with
reconciliation, and the deliberate SEVENTYFIVE_MOVE termination mapping (v2).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError as SAIntegrityError

from zugzwang_core.domain.errors import PersistenceError
from zugzwang_runtime.persistence.cognition import (
    CognitionJournal,
    DecisionJournalError,
)
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

POLICY_HASH = "b" * 64
DECISION_ID = "dec-cb0001-0000"
STEP_ID = "st-cb0001"
SESSION_ID = "sess-cb0001"
ROOT_NODE = "node-cb0001-root"


@pytest.fixture()
def journal(tmp_path):
    """Baseline copy upgraded to head (0001→0007) with seeded parents."""
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    conn = engine.connect()
    _seed_baseline(conn)
    conn.commit()
    conn.close()
    journal = CognitionJournal(database)
    journal.ensure_state_snapshot(
        state_key="state_key:v2:" + "a" * 64,
        state_schema_version="state/v2",
        rules_version="standard/v1",
        variant="standard",
        position_key="position_key:v2:" + "a" * 64,
        history_completeness="complete",
        state_artifact_id=_ART,
    )
    journal.create_decision(
        decision_id=DECISION_ID,
        step_id=STEP_ID,
        decision_ordinal=0,
        search_session_id=SESSION_ID,
        root_state_key="state_key:v2:" + "a" * 64,
        strategy_id="chess.grounded",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config_artifact_id=_ART,
    )
    journal.bind_node(
        decision_id=DECISION_ID,
        node_id=ROOT_NODE,
        state_key="state_key:v2:" + "a" * 64,
        depth_plies=0,
        created_sequence=0,
    )
    return journal


_ART = "art:cb-test-payload-v1"


def _seed_baseline(conn) -> None:
    """Minimal baseline rows: artifact, run, episode, step, session, node."""
    conn.execute(
        text(
            "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
            "relative_path, created_at) VALUES (:id, 'sha256', 1, 'application/json', "
            "'cb/test.json', '2026-09-06T00:00:00Z')"
        ),
        {"id": _ART},
    )
    conn.execute(
        text(
            "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
            "declared_assistance, projection_version, assistance_violated) "
            "VALUES ('run-cb0001', 'cond-1', 'RUNNING', 'proto', 'H0', 0, 0)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, status, "
            "assistance_violated) VALUES ('ep-cb0001', 'run-cb0001', 0, 'chess.full_game', "
            "7, 'RUNNING', 0)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
            "assistance_violated) VALUES (:step_id, 'ep-cb0001', 0, 'model:main', "
            "'RUNNING', 0)"
        ),
        {"step_id": STEP_ID},
    )
    conn.execute(
        text(
            "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
            "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
            "status, created_at) "
            "VALUES (:session_id, 'run-cb0001', 'dfs', 'v1', 'cb', :root_node, '{}', "
            "'{}', 'OPEN', '2026-09-06T00:00:00Z')"
        ),
        {"session_id": SESSION_ID, "root_node": ROOT_NODE},
    )
    conn.execute(
        text(
            "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
            "trajectory_key, state_ref, depth, terminal, created_by, status) "
            "VALUES (:node_id, :session_id, 'pos:root', 'traj:root', 'cas://root', "
            "0, 0, 'perception', 'OPEN')"
        ),
        {"node_id": ROOT_NODE, "session_id": SESSION_ID},
    )


# ---------------------------------------------------------------------------
# upgrade / rollback / referential integrity
# ---------------------------------------------------------------------------


def test_upgrade_chain_reaches_0007_with_cb_tables(tmp_path) -> None:
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cb_%'")
            ).fetchall()
        }
    expected = {
        "cb_state_snapshots",
        "cb_decisions",
        "cb_node_bindings",
        "cb_rounds",
        "cb_provider_links",
        "cb_tool_operations",
        "cb_observations",
        "cb_budget_reservations",
        "cb_budget_entries",
    }
    assert expected.issubset(tables)


def test_rollback_refused_when_decision_data_exists(tmp_path) -> None:
    """PRD §23.3: DROP automático não volta ao baseline com runs/decisões novos."""
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    conn = engine.connect()
    _seed_baseline(conn)
    conn.commit()
    conn.close()
    journal = CognitionJournal(database)
    journal.ensure_state_snapshot(
        state_key="state_key:v2:" + "a" * 64,
        state_schema_version="state/v2",
        rules_version="standard/v1",
        variant="standard",
        position_key="position_key:v2:" + "a" * 64,
        history_completeness="complete",
        state_artifact_id=_ART,
    )
    journal.create_decision(
        decision_id=DECISION_ID,
        step_id=STEP_ID,
        decision_ordinal=0,
        search_session_id=SESSION_ID,
        root_state_key="state_key:v2:" + "a" * 64,
        strategy_id="chess.grounded",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config_artifact_id=_ART,
    )
    from alembic import command
    from alembic.config import Config

    from zugzwang_runtime import migration_dir

    config = Config()
    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{engine.url.database}")
    with pytest.raises((RuntimeError, PersistenceError)):
        command.downgrade(config, "0006")


def test_feature_rollback_drops_cb_m1_tables(tmp_path) -> None:
    """Rollback da feature (0007) ensaiado em copia - baseline 0001-0006 intacto."""
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()

    from alembic import command
    from alembic.config import Config

    from zugzwang_runtime import migration_dir

    config = Config()
    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{engine.url.database}")
    command.downgrade(config, "0006")

    with engine.connect() as conn:
        remaining = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cb_%'")
            ).fetchall()
        }
        legacy = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('steps','runs')"
                )
            ).fetchall()
        }
    assert not remaining
    assert legacy == {"steps", "runs"}


def test_referential_integrity_unknown_step_rejected(journal) -> None:
    with pytest.raises(SAIntegrityError):
        journal.create_decision(
            decision_id="dec-cb0002-0000",
            step_id="st-nonexistent",
            decision_ordinal=0,
            search_session_id="sess-other",
            root_state_key="state_key:v2:" + "a" * 64,
            strategy_id="chess.grounded",
            strategy_version="0.1.0",
            interaction_mode="native_tools",
            policy_hash=POLICY_HASH,
            config_artifact_id=_ART,
        )


def test_observation_requires_node_binding(journal) -> None:
    with pytest.raises(SAIntegrityError):
        journal.record_observation(
            observation_id="obs-cb0001-000001",
            decision_id=DECISION_ID,
            node_id="node-unbound",
            round_id=None,
            operation_id=None,
            kind="initial",
            payload_artifact_id=_ART,
            semantic_hash="c" * 64,
            policy_hash=POLICY_HASH,
            exposure_sequence=0,
            available_before_selection=True,
        )


# ---------------------------------------------------------------------------
# §12.2 status transitions + immutable identity
# ---------------------------------------------------------------------------


def test_decision_transitions_follow_section_12_2(journal) -> None:
    journal.transition_decision(DECISION_ID, "READY")
    journal.transition_decision(DECISION_ID, "ACTIVE")
    journal.transition_decision(DECISION_ID, "OUTCOME_UNKNOWN")
    journal.transition_decision(DECISION_ID, "READY")
    journal.transition_decision(DECISION_ID, "ACTIVE")
    journal.transition_decision(
        DECISION_ID, "SELECTED", selected_action="e2e4", selection_source="model"
    )
    assert journal.decision_status(DECISION_ID) == "SELECTED"


def test_illegal_decision_transition_is_rejected(journal) -> None:
    journal.transition_decision(DECISION_ID, "READY")
    with pytest.raises(DecisionJournalError) as exc:
        journal.transition_decision(DECISION_ID, "SELECTED")
    assert exc.value.code == "STATE_REPLAY_MISMATCH"
    assert journal.decision_status(DECISION_ID) == "READY"


def test_decision_identity_is_immutable(journal) -> None:
    conn = journal._database.engine().connect()
    with pytest.raises(SAIntegrityError):
        conn.execute(
            text(
                "UPDATE cb_decisions SET root_state_key = 'state_key:v2:' || :pad "
                "WHERE decision_id = :id"
            ),
            {"pad": "c" * 64, "id": DECISION_ID},
        )
    conn.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# idempotent tool operations
# ---------------------------------------------------------------------------


def _round(journal: CognitionJournal) -> None:
    journal.add_round(
        round_id=f"{DECISION_ID}:round-0001",
        decision_id=DECISION_ID,
        ordinal=1,
        purpose="explore",
        context_artifact_id=_ART,
    )


def test_tool_operation_is_idempotent(journal) -> None:
    """TEST-034 (persistência): retry com a mesma chave não duplica efeito."""
    _round(journal)
    kwargs = {
        "operation_id": "operation_id:v2:" + "e" * 64,
        "decision_id": DECISION_ID,
        "round_id": f"{DECISION_ID}:round-0001",
        "provider_tool_call_id": "call-1",
        "idempotency_key": "op-key-0001",
        "tool_name": "board_observe",
        "arguments_hash": "d" * 64,
        "arguments_artifact_id": _ART,
    }
    operation_id, created = journal.record_tool_operation(**kwargs)
    assert created is True

    replay = dict(kwargs)
    replay["provider_tool_call_id"] = "call-1-retry"  # retry re-registers the call
    operation_id_2, created_2 = journal.record_tool_operation(**replay)
    assert created_2 is False
    assert operation_id_2 == operation_id


# ---------------------------------------------------------------------------
# append-only budget journal, reconciliation
# ---------------------------------------------------------------------------


def _reserve(journal: CognitionJournal, reservation_id: str, amount: int) -> None:
    journal.reserve_budget(
        reservation_id=reservation_id,
        decision_id=DECISION_ID,
        owner_kind="tool_operation",
        owner_id=reservation_id,
        unit="tool_operations",
        amount=amount,
        evidence_artifact_id=_ART,
    )


def test_idempotency_replay_with_divergent_arguments_is_rejected(journal) -> None:
    """Repetir a chave com tool/argumentos divergentes é violação, não nova operação."""
    _round(journal)
    kwargs = {
        "operation_id": "operation_id:v2:" + "e" * 64,
        "decision_id": DECISION_ID,
        "round_id": f"{DECISION_ID}:round-0001",
        "provider_tool_call_id": "call-1",
        "idempotency_key": "op-key-0001",
        "tool_name": "board_observe",
        "arguments_hash": "d" * 64,
        "arguments_artifact_id": _ART,
    }
    journal.record_tool_operation(**kwargs)
    divergent = dict(kwargs, arguments_hash="9" * 64)
    with pytest.raises(DecisionJournalError) as exc:
        journal.record_tool_operation(**divergent)
    assert exc.value.code == "STATE_REPLAY_MISMATCH"


def test_release_returns_unused_reservation(journal) -> None:
    _reserve(journal, "res-rel", 7)
    journal.release_budget(
        decision_id=DECISION_ID,
        reservation_id="res-rel",
        unit="tool_operations",
        evidence_artifact_id=_ART,
    )
    report = journal.reconcile_budget(DECISION_ID)
    assert report["tool_operations"]["remaining"] == 7


def test_budget_journal_is_append_only(journal) -> None:
    _reserve(journal, "res-1", 10)
    conn = journal._database.engine().connect()
    with pytest.raises(SAIntegrityError):
        conn.execute(text("UPDATE cb_budget_entries SET delta_used = 99"))
    conn.rollback()
    with pytest.raises(SAIntegrityError):
        conn.execute(text("DELETE FROM cb_budget_entries"))
    conn.rollback()
    conn.close()


def test_settlement_cannot_exceed_reservation(journal) -> None:
    _reserve(journal, "res-2", 5)
    with pytest.raises(DecisionJournalError) as exc:
        journal.settle_budget(
            decision_id=DECISION_ID,
            reservation_id="res-2",
            unit="tool_operations",
            used=6,
            evidence_artifact_id=_ART,
        )
    assert exc.value.code == "BUDGET_INSUFFICIENT"
    report = journal.reconcile_budget(DECISION_ID)
    assert report["tool_operations"]["remaining"] == 5


def test_adjustment_appends_without_erasing_history(journal) -> None:
    """§21: uso real maior que estimado entra como ajuste com evidência."""
    _reserve(journal, "res-3", 5)
    journal.adjust_budget(
        decision_id=DECISION_ID,
        reservation_id="res-3",
        unit="tool_operations",
        delta_reserved=3,
        delta_used=0,
        evidence_artifact_id=_ART,
    )
    journal.settle_budget(
        decision_id=DECISION_ID,
        reservation_id="res-3",
        unit="tool_operations",
        used=8,
        evidence_artifact_id=_ART,
    )
    report = journal.reconcile_budget(DECISION_ID)
    assert report["tool_operations"] == {"reserved": 8, "used": 8, "remaining": 0}


def test_budget_reconciliation_stays_non_negative(journal) -> None:
    _reserve(journal, "res-4", 4)
    journal.settle_budget(
        decision_id=DECISION_ID,
        reservation_id="res-4",
        unit="tool_operations",
        used=4,
        evidence_artifact_id=_ART,
    )
    report = journal.reconcile_budget(DECISION_ID)
    assert report["tool_operations"]["remaining"] == 0
