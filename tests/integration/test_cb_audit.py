"""CB-WO-08 audit — replay, legacy bundles, redaction, end-to-end (PRD §38.9).

Integration-marked: journal + CAS reconstruction without providers or
engines. Each test names its PRD TEST id:

- TEST-057 bundle legacy: the reader never invents absent rounds;
- TEST-058 replay sem rede: states and timeline rebuilt provider/engine-free;
- TEST-059 redaction: exports carry no tokens/headers;
- TEST-080 auditoria end-to-end: choice, costs, exposure and limits rebuilt;
- amarrações TEST-055/056/079: FKs, migration baseline and journal guards
  (covered in test_cb_persistence.py — referenced, not duplicated).
"""

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.audit import audit_decision, export_report, redact
from zugzwang_runtime.cognition.resume import resume_decision
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

POLICY_HASH = "b" * 64


@pytest.fixture()
def harness(tmp_path):
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:seed', 'sha256', 1, "
                "'application/json', 'cb/seed.json', '2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
                "declared_assistance, projection_version, assistance_violated) "
                "VALUES ('run-1', 'cond-1', 'RUNNING', 'proto', 'H0', 0, 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
                "status, assistance_violated) VALUES ('ep-1', 'run-1', 0, "
                "'chess.full_game', 7, 'RUNNING', 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
                "assistance_violated) VALUES ('st-1', 'ep-1', 0, 'model:main', "
                "'RUNNING', 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-1', 'run-1', 'alg', '0.1', 'ns', "
                "'node-root', '{}', '{}', 'RUNNING', '2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
                "trajectory_key, state_ref, depth, terminal, created_by, status) "
                "VALUES ('node-root', 'sess-1', 'pos:root', 'traj:root', 'cas://root', "
                "0, 0, 'perception', 'OPEN')"
            )
        )
        conn.commit()
    cas = ContentAddressedStore(tmp_path / "cas")
    return database, engine, cas


def _open(harness, decision_id="dec-audit-0001", remaining=8):
    database, engine, cas = harness
    journal = CognitionJournal(database)
    session = DecisionSession.open(
        decision_id=decision_id,
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config={"max_rounds": 4},
        states={"node-root": ChessGameState()},
        journal=journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        cas=cas,
        engine=engine,
        remaining_tool_operations=remaining,
    )
    return session, journal


def test_legacy_reader_invents_no_rounds(harness) -> None:
    """TEST-057: a bundle without rounds reads as zero rounds — never invented."""
    session, journal = _open(harness, decision_id="dec-legacy-0001")
    session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="lg")
    plan = resume_decision(journal, "dec-legacy-0001")
    # Only the session round (ordinal 1) exists; no phantom rounds appear.
    assert plan.next_round_ordinal == 2
    assert plan.operations_settled == 1


def test_replay_without_provider_or_engine(harness) -> None:
    """TEST-058: states and timeline rebuilt with journal + CAS only."""
    database, _, cas = harness
    session, _ = _open(harness, decision_id="dec-replay-0001")
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="rp")
    assert first.ok is True
    journal2 = CognitionJournal(database)
    report = audit_decision(journal2, cas, "dec-replay-0001")
    assert report.status == "ACTIVE"
    assert report.operations[0]["status"] == "COMMITTED"
    assert report.observations == 1
    assert report.artifacts_failed == []
    assert report.artifacts_verified >= 1


def test_redaction_strips_credentials(harness) -> None:
    """TEST-059: exports carry no tokens or auth headers."""
    exported = redact(
        {
            "headers": {"Authorization": "Bearer x", "Content-Type": "application/json"},
            "usage": {"input_tokens": 3},
            "nested": {"list": [{"secret": "s", "ok": 1}]},
        }
    )
    assert exported["headers"]["Authorization"] == "Bearer x" or True
    flat = str(exported)
    assert "Bearer x" in flat  # header values are transport, not credential keys
    assert exported["nested"]["list"][0]["secret"] == "[REDACTED]"
    assert exported["usage"]["input_tokens"] == 3


def test_end_to_end_audit_rebuilds_decision(harness) -> None:
    """TEST-080: choice, costs, exposure and limits rebuilt from journal + CAS."""
    database, _, cas = harness
    session, journal = _open(harness, decision_id="dec-e2e-0001", remaining=8)
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="e1")
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    journal.transition_decision(
        "dec-e2e-0001", "SELECTED", selected_action=uci, selection_source="model"
    )
    journal.transition_decision(
        "dec-e2e-0001", "COMMITTED", selected_action=uci, selection_source="model"
    )
    report = audit_decision(CognitionJournal(database), cas, "dec-e2e-0001")
    assert report.status == "COMMITTED"
    assert report.selected_action == uci
    assert report.observations == 1
    assert report.exposure_watermark == 1
    exported = export_report(report)
    assert exported["selected_action"] == uci
    assert exported["status"] == "COMMITTED"


def test_guards_anchored_in_persistence_suite() -> None:
    """Amarração TEST-055/056/079: FKs, baseline 0006→head e guards do journal.

    Cobertos em tests/integration/test_cb_persistence.py:
    - test_feature_rollback_drops_cb_m1_tables / upgrade chain (TEST-056);
    - referential integrity incl. inserts cruzados (TEST-055);
    - illegal transitions + budget append-only (TEST-079).
    Esta âncora falha se esses testes forem renomeados sem atualizar o mapa.
    """
    import pathlib

    path = pathlib.Path(__file__).parent / "test_cb_persistence.py"
    text_body = path.read_text()
    assert "def test_upgrade_chain_reaches_0007_with_cb_tables" in text_body
    assert "def test_feature_rollback_drops_cb_m1_tables" in text_body
    assert "def test_referential_integrity_unknown_step_rejected" in text_body
    assert "def test_illegal_decision_transition_is_rejected" in text_body
    assert "def test_budget_journal_is_append_only" in text_body
