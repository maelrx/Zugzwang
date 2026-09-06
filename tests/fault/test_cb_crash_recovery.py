"""ZGW-0101 — crash recovery in a REAL new process (PRD §14.5, TEST-037..041).

Each scenario runs a child interpreter against a scratch workspace, performs
partial decision work and hard-exits (``os._exit``) at a fault point. The
parent (a different process than the one that wrote the rows) reopens the
journal + CAS and asserts STATE AND EVIDENCE — not counters:

- S1 crash mid-decision (after a committed+exposed operation): resume
  reconstructs nodes with FENs, the exposure transcript with payloads and the
  journal-derived budget balance; ``resume_session`` continues the decision
  in the parent process to a COMMITTED finalization;
- S2 the settle/exposure window: a COMMITTED operation without an observation
  is DETECTABLE and repairable by ``recover_missing_exposures`` without
  re-executing any effect;
- S3 a crash leaving an operation PREPARED: ``settle_stale_operations`` fails
  it explicitly; a retry under the SAME key never re-executes (no settled
  result), a fresh key does.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import (
    ChessGameState,
    StandardChessEnvironment,
)
from zugzwang_core.domain.artifacts import ArtifactPayload
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.loop import CognitiveLoop
from zugzwang_runtime.cognition.resume import (
    recover_missing_exposures,
    resume_decision,
    resume_session,
    settle_stale_operations,
)
from zugzwang_runtime.cognition.session import DecisionSession, cas_artifact_loader
from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.fault

POLICY_HASH = "b" * 64

_CHILD_COMMON = textwrap.dedent(
    """
    import json, os, sys
    from sqlalchemy import text
    from zugzwang_chess.cognition import ChessPerception
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
    from zugzwang_runtime.artifacts.cas import ContentAddressedStore
    from zugzwang_runtime.cognition.session import DecisionSession
    from zugzwang_runtime.persistence.cognition import CognitionJournal
    from zugzwang_runtime.persistence.database import Database
    from zugzwang_runtime.persistence.repositories import SchemaManager

    POLICY = "b" * 64
    from pathlib import Path
    workspace = sys.argv[1]
    database = Database(Path(workspace) / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        for stmt in [
            "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
            "relative_path, created_at) VALUES ('art:seed','sha256',1,"
            "'application/json','cb/seed.json','2026-09-06T00:00:00Z')",
            "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
            "declared_assistance, projection_version, assistance_violated) "
            "VALUES ('run-1','cond-1','RUNNING','proto','H0',0,0)",
            "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
            "status, assistance_violated) VALUES ('ep-1','run-1',0,"
            "'chess.full_game',7,'RUNNING',0)",
            "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
            "assistance_violated) VALUES ('st-1','ep-1',0,'model:main','RUNNING',0)",
            "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
            "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
            "status, created_at) VALUES ('sess-1','run-1','alg','0.1','ns',"
            "'node-root','{}','{}','RUNNING','2026-09-06T00:00:00Z')",
            "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
            "trajectory_key, state_ref, depth, terminal, created_by, status) "
            "VALUES ('node-root','sess-1','pos:root','traj:root','cas://root',"
            "0,0,'perception','OPEN')",
        ]:
            conn.execute(text(stmt))
        conn.commit()
    cas = ContentAddressedStore(Path(workspace) / "cas")
    journal = CognitionJournal(database)
    session = DecisionSession.open(
        decision_id="dec-crash-0001", step_id="st-1", decision_ordinal=0,
        search_session_id="sess-1", strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0", interaction_mode="native_tools",
        policy_hash=POLICY, config={}, max_model_calls=4,
        states={"node-root": ChessGameState()}, journal=journal,
        perception=ChessPerception(environment=StandardChessEnvironment(),
                                   rules_version="standard/v1", policy_hash=POLICY),
        cas=cas, engine=engine,
    )
    """
)


def _run_child(script: str, workspace: Path) -> None:
    code = _CHILD_COMMON + textwrap.dedent(script)
    result = subprocess.run(
        [sys.executable, "-c", code, str(workspace)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    # The child exits via os._exit(1) at its fault point by design; a crash
    # BEFORE the fault point surfaces as a Python traceback on stderr.
    assert "Traceback" not in result.stderr, result.stderr


@pytest.fixture()
def workspace(tmp_path):
    path = tmp_path / "ws"
    path.mkdir()
    return path


def _state_loader(database, cas):
    env = StandardChessEnvironment()

    def load(state_key: str):
        with CognitionJournal(database).connect() as conn:
            row = conn.execute(
                text("SELECT state_artifact_id FROM cb_state_snapshots WHERE state_key = :k"),
                {"k": state_key},
            ).fetchone()
        if row is None:
            return None
        data = cas_artifact_loader(cas)(row[0])
        if data is None:
            return None
        return env.restore(
            ArtifactPayload(media_type="application/x-zugzwang-chess-state+json", data=data)
        )

    return load


def test_s1_crash_mid_decision_resumes_and_commits(workspace) -> None:
    _run_child(
        """
        session.execute("board_observe", {"node_id": "node-root"},
                        idempotency_key="c1-observe")
        probe = session.execute("board_observe", {"node_id": "node-root"},
                                idempotency_key="c1-probe")
        action_id = probe.result["packet"]["legal_actions"]["items"][0]["action_id"]
        session.execute("board_expand",
                        {"node_id": "node-root", "action_ids": [action_id]},
                        idempotency_key="c1-expand")
        os._exit(1)
        """,
        workspace,
    )
    database = Database(workspace / "state.db", wal_policy="ephemeral")
    engine = database.open()
    cas = ContentAddressedStore(workspace / "cas")
    journal = CognitionJournal(database)
    plan = resume_decision(
        journal,
        "dec-crash-0001",
        state_loader=_state_loader(database, cas),
        payload_loader=cas_artifact_loader(cas),
    )
    # Evidence, not counters: the root state FEN, the transcript payload…
    assert plan.status == "ACTIVE"
    assert plan.nodes[0]["fen"] == ChessGameState().fen
    assert plan.nodes[0]["node_id"] == "node-root"
    expansions = [t for t in plan.transcript if t["kind"] == "expand"]
    assert expansions, "the crash left the committed expansion visible"
    raw_payload = expansions[0]["payload"]
    payload = json.loads(raw_payload) if isinstance(raw_payload, bytes) else raw_payload
    assert payload["results"][0]["child_node_id"]
    # …and the budget balance from the JOURNAL (the child's memory is gone).
    tool_balance = plan.budget_balance["tool_operations"]
    assert tool_balance["reserved"] == 32
    assert tool_balance["used"] >= 3, "atomic settle debited every settled operation"
    assert tool_balance["remaining"] == 32 - tool_balance["used"]

    # Continuation in THIS new process: rebuild the session and finalize.
    resumed = resume_session(
        plan=plan,
        journal=journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        cas=cas,
        engine=engine,
    )
    backend = FakeCognitiveBackend(
        [
            lambda messages: {
                "tool": "board_finalize",
                "arguments": {"node_id": resumed.root_node_id or "node-root", "action": "e2e4"},
            }
        ]
    )
    loop = CognitiveLoop(
        decision_id=resumed.decision_id,
        journal=resumed.journal,
        broker_factory=resumed.new_broker_for_round,
        backend=backend,
        context_artifact_id=resumed.round_context_artifact_id,
        max_rounds=3,
    )
    import asyncio

    result = asyncio.run(loop.run())
    assert result.status == "COMMITTED"
    assert result.selected_action == "e2e4"
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = 'dec-crash-0001'")
        ).fetchone()[0]
    assert status == "COMMITTED"


def test_s2_committed_without_exposure_is_detected_and_repaired(workspace) -> None:
    _run_child(
        """
        envelope = session.execute("board_observe", {"node_id": "node-root"},
                                   idempotency_key="c2-observe")
        assert envelope.ok
        # Simulate the LEGACY window with a SECOND committed operation whose
        # observation row was never written (observations are immutable, so a
        # fresh row is the only honest way to model a pre-fix crash).
        with journal.connect() as conn:
            row = conn.execute(text(
                "SELECT round_id, provider_tool_call_id, command_ordinal, "
                "idempotency_key, tool_name, arguments_hash, arguments_artifact_id, "
                "result_artifact_id, created_at FROM cb_tool_operations "
                "WHERE decision_id = 'dec-crash-0001' AND status = 'COMMITTED' "
                "LIMIT 1")).fetchone()
            conn.execute(text(
                "INSERT INTO cb_tool_operations (operation_id, decision_id, round_id, "
                "provider_tool_call_id, command_ordinal, idempotency_key, tool_name, "
                "arguments_hash, arguments_artifact_id, status, result_artifact_id, "
                "completed_at, created_at) VALUES ('operation_id:v2:legacy-window', "
                "'dec-crash-0001', :round_id, 'legacy-window', 99, 'legacy-window', "
                ":tool_name, :arguments_hash, :arguments_artifact_id, 'COMMITTED', "
                ":result_artifact_id, :created_at, :created_at)"
            ), {"round_id": row[0], "tool_name": row[4],
                "arguments_hash": row[5], "arguments_artifact_id": row[6],
                "result_artifact_id": row[7], "created_at": row[8]})
            conn.commit()
        os._exit(1)
        """,
        workspace,
    )
    database = Database(workspace / "state.db", wal_policy="ephemeral")
    engine = database.open()
    cas = ContentAddressedStore(workspace / "cas")
    journal = CognitionJournal(database)
    with engine.connect() as conn:
        committed = conn.execute(
            text(
                "SELECT COUNT(*) FROM cb_tool_operations "
                "WHERE decision_id = 'dec-crash-0001' AND status = 'COMMITTED'"
            )
        ).scalar_one()
        exposed = conn.execute(
            text("SELECT COUNT(*) FROM cb_observations WHERE decision_id = 'dec-crash-0001'")
        ).scalar_one()
    assert committed == 2 and exposed == 1, "the window is real and detectable"

    repaired = recover_missing_exposures(journal, "dec-crash-0001", loader=cas_artifact_loader(cas))
    assert repaired == 1
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT node_id, payload_artifact_id FROM cb_observations "
                "WHERE decision_id = 'dec-crash-0001'"
            )
        ).fetchone()
    assert row[0] == "node-root", "node identity rebuilt from the operation arguments"
    assert cas_artifact_loader(cas)(row[1]) is not None
    # Idempotent: nothing left to repair.
    assert (
        recover_missing_exposures(journal, "dec-crash-0001", loader=cas_artifact_loader(cas)) == 0
    )


def test_s3_prepared_orphan_fails_explicitly_and_retry_is_safe(workspace) -> None:
    _run_child(
        """
        import os
        from zugzwang_runtime.cognition.broker import CognitionToolBroker

        def crashing(self, tool, arguments):
            os._exit(1)  # crash AFTER record (PREPARED), BEFORE settle

        CognitionToolBroker._preflight = crashing
        session.execute("board_observe", {"node_id": "node-root"},
                        idempotency_key="c3-kill")
        """,
        workspace,
    )
    database = Database(workspace / "state.db", wal_policy="ephemeral")
    engine = database.open()
    cas = ContentAddressedStore(workspace / "cas")
    journal = CognitionJournal(database)
    plan = resume_decision(journal, "dec-crash-0001")
    assert len(plan.operations_open) == 1, "the PREPARED orphan is visible"

    assert settle_stale_operations(journal, "dec-crash-0001") == 1
    plan2 = resume_decision(journal, "dec-crash-0001")
    assert plan2.operations_open == []
    with engine.connect() as conn:
        status = conn.execute(
            text(
                "SELECT status, error_code FROM cb_tool_operations "
                "WHERE decision_id = 'dec-crash-0001' AND idempotency_key = 'c3-kill'"
            )
        ).fetchone()
    assert status == ("FAILED", "PERSISTENCE_FAILED"), "never marked COMMITTED"

    # The SAME key never re-executes the effect (replay of an unsettled op is
    # refused); a FRESH key runs normally in the resumed session.
    resumed = resume_session(
        plan=resume_decision(
            journal,
            "dec-crash-0001",
            state_loader=_state_loader(database, cas),
            payload_loader=cas_artifact_loader(cas),
        ),
        journal=journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        cas=cas,
        engine=engine,
    )
    same_key = resumed.execute("board_observe", {"node_id": "node-root"}, idempotency_key="c3-kill")
    assert same_key.ok is False
    fresh = resumed.execute("board_observe", {"node_id": "node-root"}, idempotency_key="c3-retry")
    assert fresh.ok is True
    assert fresh.result is not None and fresh.result["content_hash"]


def test_budget_error_matrix_and_idempotent_retry(harness_factory) -> None:
    """TEST-036 zero-balance: an invalid request at ZERO balance settles
    REJECTED without ValueError and without stranding the row PREPARED."""
    session = harness_factory(remaining=0)
    # Valid request at zero balance: refused before execution.
    refused = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="z-obs")
    assert refused.ok is False
    assert refused.error is not None
    assert refused.error.code == "BUDGET_INSUFFICIENT"
    # Invalid request at zero balance: client error settles, nothing raises.
    invalid = session.execute("board_observe", {"node_id": ""}, idempotency_key="z-bad")
    assert invalid.ok is False
    assert invalid.error is not None
    assert invalid.error.code == "INVALID_ARGUMENTS"
    _database, engine, _cas = harness_factory.harness["harness"]
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT idempotency_key, status FROM cb_tool_operations WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchall()
    statuses = dict(rows)
    assert statuses["z-obs"] == "REJECTED"
    assert statuses["z-bad"] == "REJECTED", "no PREPARED stranding at zero balance"


@pytest.fixture()
def harness_factory(tmp_path):
    made: dict[str, Any] = {}

    def factory(remaining: int):
        database = Database(tmp_path / "budget.db", wal_policy="ephemeral")
        engine = database.open()
        SchemaManager(engine).upgrade()
        with engine.connect() as conn:
            for stmt in (
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:seed','sha256',1,"
                "'application/json','cb/seed.json','2026-09-06T00:00:00Z')",
                "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
                "declared_assistance, projection_version, assistance_violated) "
                "VALUES ('run-1','cond-1','RUNNING','proto','H0',0,0)",
                "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
                "status, assistance_violated) VALUES ('ep-1','run-1',0,"
                "'chess.full_game',7,'RUNNING',0)",
                "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
                "assistance_violated) VALUES ('st-1','ep-1',0,'model:main','RUNNING',0)",
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-1','run-1','alg','0.1','ns',"
                "'node-root','{}','{}','RUNNING','2026-09-06T00:00:00Z')",
                "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
                "trajectory_key, state_ref, depth, terminal, created_by, status) "
                "VALUES ('node-root','sess-1','pos:root','traj:root','cas://root',"
                "0,0,'perception','OPEN')",
            ):
                conn.execute(text(stmt))
            conn.commit()
        cas = ContentAddressedStore(tmp_path / "cas")
        session = DecisionSession.open(
            decision_id="dec-budget-0001",
            step_id="st-1",
            decision_ordinal=0,
            search_session_id="sess-1",
            strategy_id="chess.cognitive_navigation",
            strategy_version="0.2.0",
            interaction_mode="native_tools",
            policy_hash=POLICY_HASH,
            config={},
            states={"node-root": ChessGameState()},
            journal=CognitionJournal(database),
            perception=ChessPerception(
                environment=StandardChessEnvironment(),
                rules_version="standard/v1",
                policy_hash=POLICY_HASH,
            ),
            cas=cas,
            engine=engine,
            remaining_tool_operations=remaining,
        )
        made["harness"] = (database, engine, cas)
        return session

    factory.harness = made  # type: ignore[attr-defined]
    return factory
