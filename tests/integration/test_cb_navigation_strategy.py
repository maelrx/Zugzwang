"""ZGW-0101 — ``chess.cognitive_navigation`` drives the productive loop.

The strategy (moved to the runtime so chess never imports runtime — TEST-062)
must produce a DecisionTrace whose CallRecords come from the effective infer
calls, whose candidate carries origin="model" only for the action the loop
committed, and whose descriptor stays on the conservative R7/H4 default while
G-CB-01 is pending (§48.3).
"""

import asyncio

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.ports.strategy import DecisionContext
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.navigation import CognitiveNavigationStrategy
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend
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
    return database, engine, ContentAddressedStore(tmp_path / "cas")


def test_descriptor_stays_conservative_until_gate() -> None:
    """G-CB-01 pending: R7/H4/K0 — never a self-granted regime bump."""
    descriptor = CognitiveNavigationStrategy().descriptor
    assert descriptor.declared_regime == "R7"
    assert descriptor.declared_assistance_h == "H4"
    assert descriptor.declared_assistance_k == "K0"
    assert descriptor.strategy_id == "chess.cognitive_navigation"


def test_decide_runs_productive_loop_and_returns_real_trace(harness) -> None:
    """decide() runs the loop over the session; trace carries real evidence."""
    database, engine, cas = harness
    session = DecisionSession.open(
        decision_id="dec-nav-0001",
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
    )
    backend = FakeCognitiveBackend(
        [
            lambda messages: {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
            lambda messages: {
                "tool": "board_finalize",
                "arguments": {"node_id": "node-root", "action": "e2e4"},
            },
        ]
    )
    from zugzwang_core.ports.model import ModelRef

    strategy = CognitiveNavigationStrategy(max_rounds=4)
    context = DecisionContext(
        run_id="run-1",
        episode_id="ep-1",
        step_id="st-1",
        model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
        decision_session=session,
    )
    trace = asyncio.run(strategy.decide({"node_id": "node-root"}, context))
    assert trace.final_action == "e2e4"
    assert trace.termination_reason == "selected"
    assert len(trace.calls) == 2, "one CallRecord per effective infer call"
    assert all(call.response_ok for call in trace.calls)
    assert trace.calls[0].usage.input_tokens == 17, "usage from the effective call"
    assert all(call.request_fingerprint.startswith("reqfp:v1:") for call in trace.calls)
    assert trace.candidates[0].origin == "model"
    # The decision really committed through the journal.
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, selected_action, selection_source FROM cb_decisions "
                "WHERE decision_id = 'dec-nav-0001'"
            )
        ).fetchone()
    assert row[0] == "COMMITTED" and row[1] == "e2e4" and row[2] == "model"


def test_decide_requires_session_and_backend() -> None:
    """Without a §26.1 session the strategy fails explicitly, never degrades."""
    from zugzwang_core.ports.model import ModelRef

    strategy = CognitiveNavigationStrategy()
    context = DecisionContext(
        run_id="run-1",
        episode_id="ep-1",
        step_id="st-1",
        model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
        backend=FakeCognitiveBackend([]),
        tools={},
        seed=7,
    )
    with pytest.raises(ValueError, match="decision_session"):
        asyncio.run(strategy.decide({"node_id": "node-root"}, context))
