"""CB-WO-05 acceptance — authorized L0 tool broker (PRD §38.6, §11, §42.6).

Offline, deterministic, no providers or engines: a DecisionSession is opened
over a scratch SQLite + CAS, then the broker is exercised through the only
authorized path (session.execute). Each test names the PRD TEST id it covers:

- TEST-019 node scope denied before any projection is read;
- TEST-020 oversized request rejected without allocation or persistence;
- TEST-021 tool-internal failure closes failed with OUTPUT_CONTRACT_VIOLATION;
- TEST-031 shared budget pool is not reset by a second broker/focus;
- TEST-032 concurrent decisions cannot over-reserve the shared pool;
- TEST-033 repeated query with a fresh key records a new exposure;
- TEST-034 idempotent retry repeats the result with no new charge;
- TEST-035 same key with divergent arguments conflicts (STATE_REPLAY_MISMATCH);
- TEST-036 insufficient budget refuses the batch before any item runs;
- TEST-077 same parent + action never yields a duplicated structural edge;
- TEST-078 tool results respect the definition order of the batch.
"""

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.broker import CognitionToolBroker
from zugzwang_runtime.cognition.session import (
    DecisionSession,
    cas_artifact_loader,
    cas_artifact_sink,
)
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

POLICY_HASH = "b" * 64
CONFIG = {"beam": "smoke"}


@pytest.fixture()
def harness(tmp_path):
    """Scratch DB + CAS with baseline parents and one search node."""
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


def _perception() -> ChessPerception:
    return ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
    )


def _open_session(harness, decision_id="dec-test-0001", remaining=32) -> DecisionSession:
    database, engine, cas = harness
    journal = CognitionJournal(database)
    return DecisionSession.open(
        decision_id=decision_id,
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.grounded",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config=dict(CONFIG),
        states={"node-root": ChessGameState()},
        journal=journal,
        perception=_perception(),
        cas=cas,
        engine=engine,
        remaining_tool_operations=remaining,
    )


def _operations(engine, decision_id):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT operation_id, tool_name, status, error_code FROM cb_tool_operations "
                "WHERE decision_id = :decision_id ORDER BY created_at, operation_id"
            ),
            {"decision_id": decision_id},
        ).fetchall()


def _observations(engine, decision_id):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT observation_id, kind, exposure_sequence FROM cb_observations "
                "WHERE decision_id = :decision_id ORDER BY exposure_sequence"
            ),
            {"decision_id": decision_id},
        ).fetchall()


def test_observe_round_trip_records_operation_and_observation(harness) -> None:
    """Baseline: observe commits, charges one op, journals one exposure."""
    _, engine, _ = harness
    session = _open_session(harness)
    envelope = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="k1")
    assert envelope.ok is True
    assert envelope.error is None
    assert envelope.result is not None
    assert envelope.result["packet"]["legal_actions"]["total_count"] == 20
    assert envelope.meta.logical_operations_charged == 1
    assert envelope.meta.semantic_hash is not None

    operations = _operations(engine, session.decision_id)
    assert len(operations) == 1
    assert operations[0][1] == "board_observe"
    assert operations[0][2] == "COMMITTED"

    observations = _observations(engine, session.decision_id)
    assert len(observations) == 1
    assert observations[0][1] == "view"


def test_foreign_node_denied_before_projection(harness) -> None:
    """TEST-019: node outside the decision scope is denied with NODE_SCOPE_MISMATCH."""
    session = _open_session(harness)
    envelope = session.execute("board_observe", {"node_id": "node-ghost"}, idempotency_key="k19")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "NODE_SCOPE_MISMATCH"
    # No observation confirms the foreign node's (non-)existence in the timeline.
    assert _observations(harness[1], session.decision_id) == []


def test_oversized_request_rejected_without_persistence(harness) -> None:
    """TEST-020: oversized arguments rejected before allocation or persistence."""
    _, engine, _ = harness
    session = _open_session(harness)
    envelope = session.execute(
        "board_inspect",
        {"node_id": "node-root", "query": "terminal", "pad": "x" * 9000},
        idempotency_key="k20",
    )
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "INVALID_ARGUMENTS"
    assert _operations(engine, session.decision_id) == []
    assert _observations(engine, session.decision_id) == []


def test_unknown_tool_rejected_from_catalog(harness) -> None:
    """TEST-021 (catalog half): a tool outside the catalog never executes."""
    session = _open_session(harness)
    envelope = session.execute("board_evaluate", {"node_id": "node-root"}, idempotency_key="k21")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "TOOL_NOT_ALLOWED"


def test_tool_internal_failure_closes_failed(harness, monkeypatch) -> None:
    """TEST-021 (fail-closed half): internal failure settles FAILED, never COMMITTED."""
    _, engine, _ = harness
    session = _open_session(harness)
    monkeypatch.setattr(ChessPerception, "build_packet", lambda *args, **kwargs: 1 / 0)
    envelope = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="k21b")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "OUTPUT_CONTRACT_VIOLATION"
    operations = _operations(engine, session.decision_id)
    assert len(operations) == 1
    assert operations[0][2] == "FAILED"


def test_shared_pool_survives_focus_change(harness) -> None:
    """TEST-031: a second broker over the same pool keeps the remaining budget."""
    database, engine, cas = harness
    session = _open_session(harness, decision_id="dec-focus", remaining=4)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="focus-a")
    assert first.ok is True
    # A "focus change" constructs a second broker over the same open round and
    # the same pool object — the ceiling is not reset.
    journal = CognitionJournal(database)
    shared = session._broker._budget
    second = CognitionToolBroker(
        decision_id="dec-focus",
        round_id="dec-focus:round-0001",
        round_ordinal=1,
        journal=journal,
        perception=_perception(),
        policy_hash=POLICY_HASH,
        states={"node-root": ChessGameState()},
        budget=shared,
        artifact_sink=cas_artifact_sink(cas, engine, lambda: "2026-09-06T00:00:00Z"),
        artifact_loader=cas_artifact_loader(cas),
    )
    envelope = second.execute("board_observe", {"node_id": "node-root"}, idempotency_key="focus-b")
    assert envelope.ok is True
    assert envelope.meta.remaining_tool_operations == 2


def test_concurrent_decisions_share_one_pool(harness) -> None:
    """TEST-032: two brokers on one pool cannot reserve beyond the balance."""
    database, engine, cas = harness
    session = _open_session(harness, decision_id="dec-shared", remaining=1)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="shr-a")
    assert first.ok is True
    # A concurrent broker over the same open round shares the same pool: the
    # remaining balance is 0, so even a batch of 1 is refused before execution.
    journal = CognitionJournal(database)
    concurrent = CognitionToolBroker(
        decision_id="dec-shared",
        round_id="dec-shared:round-0001",
        round_ordinal=1,
        journal=journal,
        perception=_perception(),
        policy_hash=POLICY_HASH,
        states={"node-root": ChessGameState()},
        budget=session._broker._budget,
        artifact_sink=cas_artifact_sink(cas, engine, lambda: "2026-09-06T00:00:00Z"),
        artifact_loader=cas_artifact_loader(cas),
    )
    refused = concurrent.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": ["whatever"]},
        idempotency_key="shr-b",
    )
    assert refused.ok is False
    assert refused.error is not None
    assert refused.error.code == "BUDGET_INSUFFICIENT"


def test_repeated_query_records_new_exposure(harness) -> None:
    """TEST-033: a fresh key over the same node commits again with a new exposure."""
    _, engine, _ = harness
    session = _open_session(harness)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="cache-a")
    second = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="cache-b")
    assert first.ok and second.ok
    assert first.meta.semantic_hash == second.meta.semantic_hash
    observations = _observations(engine, session.decision_id)
    assert [row[2] for row in observations] == [1, 2]


def test_idempotent_retry_repeats_result_without_charge(harness) -> None:
    """TEST-034: same key retries the stored result, never the effect."""
    session = _open_session(harness)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="idem")
    retry = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="idem")
    assert retry.ok is True
    assert retry.result == first.result
    assert retry.meta.semantic_hash == first.meta.semantic_hash
    assert retry.meta.logical_operations_charged == 0
    assert retry.meta.exposure_sequence == first.meta.exposure_sequence


def test_divergent_retry_conflicts(harness) -> None:
    """TEST-035: same key with different arguments raises STATE_REPLAY_MISMATCH."""
    session = _open_session(harness)
    first = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="clash")
    assert first.ok is True
    clash = session.execute(
        "board_inspect",
        {"node_id": "node-root", "query": "terminal"},
        idempotency_key="clash",
    )
    assert clash.ok is False
    assert clash.error is not None
    assert clash.error.code == "STATE_REPLAY_MISMATCH"


def test_insufficient_budget_refuses_batch_before_execution(harness) -> None:
    """TEST-036: the whole expand batch is refused before any item runs."""
    _, engine, _ = harness
    session = _open_session(harness, remaining=1)
    observe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="obs")
    assert observe.ok is True
    actions = [item["action_id"] for item in observe.result["packet"]["legal_actions"]["items"][:2]]
    refused = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": actions},
        idempotency_key="batch",
    )
    assert refused.ok is False
    assert refused.error is not None
    assert refused.error.code == "BUDGET_INSUFFICIENT"
    # Nothing was charged for the refused batch; only the observe debited the pool.
    assert refused.meta.remaining_tool_operations == 0
    operations = _operations(engine, session.decision_id)
    assert [row[2] for row in operations] == ["COMMITTED", "REJECTED"]


def test_expand_repeats_same_edge_without_duplication(harness) -> None:
    """TEST-077: same parent + action expand repeats the same result rows, no new edges."""
    session = _open_session(harness)
    observe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="e-obs")
    action_id = observe.result["packet"]["legal_actions"]["items"][0]["action_id"]
    first = session.execute(
        "board_expand", {"node_id": "node-root", "action_ids": [action_id]}, idempotency_key="e-a"
    )
    second = session.execute(
        "board_expand", {"node_id": "node-root", "action_ids": [action_id]}, idempotency_key="e-b"
    )
    assert first.ok and second.ok
    assert first.result["results"] == second.result["results"]
    assert len(first.result["results"]) == 1


def test_batch_definition_order_is_respected(harness) -> None:
    """TEST-078: expand results follow the action_ids order given in the batch."""
    session = _open_session(harness)
    observe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="o-obs")
    items = observe.result["packet"]["legal_actions"]["items"]
    batch = [items[3]["action_id"], items[0]["action_id"], items[1]["action_id"]]
    envelope = session.execute(
        "board_expand", {"node_id": "node-root", "action_ids": batch}, idempotency_key="o-batch"
    )
    assert envelope.ok is True
    assert [row["action_id"] for row in envelope.result["results"]] == batch
    assert envelope.meta.logical_operations_charged == len(batch)
