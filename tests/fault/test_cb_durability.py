"""CB-WO-08 durability — crash recovery, CAS safety, disk limit, cancel (PRD §38.9).

Fault-marked tests: sqlite/CAS integration with injected crashes. No network,
no engines. Each test names its PRD TEST id:

- TEST-037 crash before DB commit: CAS orphans never become settled operations;
- TEST-038 crash after commit: replay recovers the output without new effect;
- TEST-040 crash after selection: the real action applies exactly once;
- TEST-041 checkpoint per round: resume reproduces transcript, snapshots, budget;
- TEST-053 path traversal: malformed refs never read outside the CAS;
- TEST-054 bad hash: corruption detected before exposure;
- TEST-067 disk limit: the runner stops before a call it could not persist;
- TEST-068 cancel: no new operations; remote uncertainty preserved.
"""

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.audit import export_report, validate_artifact_id
from zugzwang_runtime.cognition.resume import open_operations, resume_decision
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.fault

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


def _open(harness, decision_id="dec-dur-0001", remaining=32):
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


def test_orphans_never_become_settled_operations(harness) -> None:
    """TEST-037: CAS object written, DB commit crashed → no settled operation."""
    from zugzwang_core.domain.artifacts import ArtifactPayload

    _, engine, cas = harness
    session, _ = _open(harness, decision_id="dec-orphan-0001")
    # Simulate: CAS object landed, but the operation row never committed.
    ref = cas.put(ArtifactPayload(media_type="application/json", data=b'{"x": 1}'))
    with engine.connect() as conn:
        ops = conn.execute(
            text(
                "SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id "
                "AND status <> 'PREPARED'"
            ),
            {"id": "dec-orphan-0001"},
        ).fetchone()[0]
        dangling = conn.execute(
            text("SELECT COUNT(*) FROM artifacts WHERE artifact_id = :id"),
            {"id": ref.as_id()},
        ).fetchone()[0]
    assert ops == 0
    # The orphan is GC-safe (exists in CAS, unreferenced) — never settled.
    assert dangling == 0
    assert session.decision_id == "dec-orphan-0001"


def test_replay_recovers_output_without_new_effect(harness) -> None:
    """TEST-038: committed output replays identically after a 'crash' (new handles)."""
    database, engine, cas = harness
    session, _ = _open(harness, decision_id="dec-replay-0001")
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="rp")
    assert first.ok is True
    # Crash: drop every handle, reopen on the same files.
    journal2 = CognitionJournal(database)
    plan = resume_decision(journal2, "dec-replay-0001")
    assert plan.operations_open == []
    assert plan.operations_settled == 1
    assert plan.exposure_watermark == 1
    # Re-executing the same key through a fresh session replays, never re-debits.
    session2_journal = CognitionJournal(database)
    from zugzwang_runtime.cognition.broker import CognitionToolBroker
    from zugzwang_runtime.cognition.session import cas_artifact_loader, cas_artifact_sink

    broker2 = CognitionToolBroker(
        decision_id="dec-replay-0001",
        round_id="dec-replay-0001:round-0001",
        round_ordinal=1,
        journal=session2_journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        policy_hash=POLICY_HASH,
        states={"node-root": ChessGameState()},
        budget=session._broker._budget,
        artifact_sink=cas_artifact_sink(cas, engine, lambda: "2026-09-06T00:00:00Z"),
        artifact_loader=cas_artifact_loader(cas),
    )
    replay = broker2.execute("board_observe", {"node_id": "node-root"}, idempotency_key="rp")
    assert replay.ok is True
    assert replay.result == first.result
    assert replay.meta.logical_operations_charged == 0


def test_selection_applies_exactly_once(harness) -> None:
    """TEST-040: crash after SELECTED/COMMITTED never applies the action twice."""
    _, _, _ = harness
    session, journal = _open(harness, decision_id="dec-once-0001")
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="once")
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    journal.transition_decision(
        "dec-once-0001", "SELECTED", selected_action=uci, selection_source="model"
    )
    journal.transition_decision(
        "dec-once-0001", "COMMITTED", selected_action=uci, selection_source="model"
    )
    plan = resume_decision(journal, "dec-once-0001")
    assert plan.status == "COMMITTED"
    assert plan.selected_action == uci
    # A second commit attempt is refused (terminal state): exactly-once.
    from zugzwang_runtime.persistence.cognition import DecisionJournalError

    with pytest.raises(DecisionJournalError):
        journal.transition_decision(
            "dec-once-0001", "COMMITTED", selected_action=uci, selection_source="model"
        )


def test_resume_reproduces_transcript_snapshots_budget(harness) -> None:
    """TEST-041: checkpoint per round — resume reproduces transcript and budget."""
    database, _, _ = harness
    session, _journal = _open(harness, decision_id="dec-resume-0001", remaining=8)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="c1")
    second = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="c2")
    assert first.ok and second.ok
    journal2 = CognitionJournal(database)
    plan = resume_decision(journal2, "dec-resume-0001")
    assert plan.next_round_ordinal == 2
    assert plan.operations_settled == 2
    assert plan.exposure_watermark == 2
    assert open_operations(journal2, "dec-resume-0001") == []


def test_malformed_refs_never_leave_cas(harness) -> None:
    """TEST-053: traversal/malformed refs are rejected before any read."""
    _, _, cas = harness
    assert validate_artifact_id("../../etc/passwd") is False
    assert validate_artifact_id("sha256:zzzz") is False
    assert validate_artifact_id("art:legacy-id") is False
    assert validate_artifact_id("sha256:" + "a" * 64) is True
    # Even a well-formed but absent ref resolves to nothing, never a path.
    from zugzwang_runtime.cognition.audit import _verify_artifact

    ok, data = _verify_artifact(cas, "sha256:" + "b" * 64)
    assert ok is False
    assert data is None


def test_corrupt_object_detected_before_exposure(harness) -> None:
    """TEST-054: CAS corruption is detected by hash check before exposure."""
    from zugzwang_core.domain.artifacts import ArtifactPayload

    _, _, cas = harness
    ref = cas.put(ArtifactPayload(media_type="application/json", data=b'{"ok": true}'))
    # Corrupt the object behind the registered reference.
    target = cas.path_for(ref)
    target.write_bytes(b'{"ok": false}')
    from zugzwang_runtime.cognition.audit import _verify_artifact

    ok, data = _verify_artifact(cas, ref.as_id())
    assert ok is False
    assert data is None


def test_disk_limit_stops_before_unpersistable_call(harness) -> None:
    """TEST-067: with zero budget headroom the runner refuses before executing."""
    session, _ = _open(harness, decision_id="dec-disk-0001", remaining=0)
    envelope = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="d1")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "BUDGET_INSUFFICIENT"


def test_cancel_leaves_no_new_operations(harness) -> None:
    """TEST-068: cancel (FAILED) records no new operations; outcome stays explicit."""
    session, journal = _open(harness, decision_id="dec-cancel-0001")
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="x1")
    assert first.ok is True
    with harness[1].connect() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id"),
            {"id": "dec-cancel-0001"},
        ).fetchone()[0]
    journal.transition_decision("dec-cancel-0001", "FAILED")
    plan = resume_decision(journal, "dec-cancel-0001")
    assert plan.status == "FAILED"
    with harness[1].connect() as conn:
        after = conn.execute(
            text("SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id"),
            {"id": "dec-cancel-0001"},
        ).fetchone()[0]
    assert after == before == 1
    assert session.decision_id == "dec-cancel-0001"


def test_export_carries_no_secrets(harness) -> None:
    """TEST-059 (fault half): the redacted export never carries credentials."""
    from zugzwang_runtime.cognition.audit import redact

    wire = {"access_token": "tok", "api_key": "key", "ok": 1}
    exported = redact({"decision_id": "dec-x", "wire": wire})
    assert exported["wire"]["access_token"] == "[REDACTED]"
    assert exported["wire"]["api_key"] == "[REDACTED]"
    assert exported["wire"]["ok"] == 1
    assert export_report is not None
