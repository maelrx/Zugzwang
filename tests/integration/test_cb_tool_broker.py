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

import json as _json

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.domain.cognition import action_id_v2
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


def test_foreign_node_denied_before_projection(harness, monkeypatch) -> None:
    """TEST-019: node outside the decision scope is denied with NODE_SCOPE_MISMATCH."""
    session = _open_session(harness)
    calls: list[str] = []
    original = ChessPerception.build_packet

    def _spy(self, state, node_id, **kwargs):
        calls.append(node_id)
        return original(self, state, node_id, **kwargs)

    monkeypatch.setattr(ChessPerception, "build_packet", _spy)
    envelope = session.execute("board_observe", {"node_id": "node-ghost"}, idempotency_key="k19")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "NODE_SCOPE_MISMATCH"
    # Denied before any projection is built, and the scope probe is not charged.
    assert calls == []
    assert envelope.meta.logical_operations_charged == 0
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


def test_observe_refused_at_zero_balance_before_execution(harness, monkeypatch) -> None:
    """Non-expand tools are budget-checked in preflight too: at zero balance the
    observe is REJECTED before any projection runs (fail-closed, no stuck PREPARED)."""
    session = _open_session(harness, remaining=0)
    calls: list[str] = []
    original = ChessPerception.build_packet

    def _spy(self, state, node_id, **kwargs):
        calls.append(node_id)
        return original(self, state, node_id, **kwargs)

    monkeypatch.setattr(ChessPerception, "build_packet", _spy)
    envelope = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="zero")
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "BUDGET_INSUFFICIENT"
    assert calls == []
    assert envelope.meta.logical_operations_charged == 0


def test_malformed_arguments_rejected_as_client_error(harness) -> None:
    """Absent node ids, bad cursor and unknown inspect query are INVALID_ARGUMENTS."""
    session = _open_session(harness)
    missing = session.execute("board_observe", {}, idempotency_key="m1")
    assert missing.error is not None
    assert missing.error.code == "INVALID_ARGUMENTS"
    cursor = session.execute(
        "board_observe", {"node_id": "node-root", "cursor": -1}, idempotency_key="m2"
    )
    assert cursor.error is not None
    assert cursor.error.code == "INVALID_ARGUMENTS"
    query = session.execute(
        "board_inspect",
        {"node_id": "node-root", "query": "evaluate"},
        idempotency_key="m3",
    )
    assert query.error is not None
    assert query.error.code == "INVALID_ARGUMENTS"
    other = session.execute("board_compare", {"node_id": "node-root"}, idempotency_key="m4")
    assert other.error is not None
    assert other.error.code == "INVALID_ARGUMENTS"


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


# ---------------------------------------------------------------------------
# ZGW-0101 regression — real expansion (PRD §9/§11.6; review round a2d0241).
# These probes fail on the pre-fix broker, which returned ``expanded=True``
# without transitioning, registering a child, or exposing an edge.
# ---------------------------------------------------------------------------

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FEN_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
FEN_AFTER_E4_C5 = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
FEN_AFTER_D4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"


def _state_fen(harness, state_key):
    """Recover a bound state's FEN from the durable snapshots (not memory)."""
    database, _engine, cas = harness
    journal = CognitionJournal(database)
    with journal.connect() as conn:
        row = conn.execute(
            text("SELECT state_artifact_id FROM cb_state_snapshots WHERE state_key = :k"),
            {"k": state_key},
        ).fetchone()
    assert row is not None, f"no durable snapshot for {state_key}"
    data = cas_artifact_loader(cas)(row[0])
    assert data is not None
    return _json.loads(data.decode("utf-8"))["fen"]


def _legal_action_id(session, uci):
    """action_id of a legal UCI over the complete kernel set (any page)."""
    state_key, _ = session._broker._perception.identity_keys(ChessGameState())
    return action_id_v2(state_key, uci, "uci/v1", POLICY_HASH)


def test_expand_transitions_and_child_is_observable_and_expandable(harness) -> None:
    """FR-009/§11.6: e2e4 → c7c5 — distinct children, expected FENs, alternating
    turns, growing depth, untouched root, and the returned child can be
    observed AND expanded on the next call."""
    session = _open_session(harness)
    root_before = session.execute(
        "board_observe", {"node_id": "node-root"}, idempotency_key="t-obs-root"
    )
    assert root_before.ok

    e4 = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [_legal_action_id(session, "e2e4")]},
        idempotency_key="t-e4",
    )
    d4 = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [_legal_action_id(session, "d2d4")]},
        idempotency_key="t-d4",
    )
    assert e4.ok and d4.ok, (e4.error, d4.error)
    e4_row, d4_row = e4.result["results"][0], d4.result["results"][0]
    assert e4_row["expanded"] is True and d4_row["expanded"] is True
    assert e4_row["child_node_id"] != d4_row["child_node_id"], "siblings are distinct nodes"
    assert e4_row["state_key"] != d4_row["state_key"]
    assert e4_row["depth"] == d4_row["depth"] == 1
    assert _state_fen(harness, e4_row["state_key"]) == FEN_AFTER_E4
    assert _state_fen(harness, d4_row["state_key"]) == FEN_AFTER_D4

    # The child is a first-class node: observable…
    child_obs = session.execute(
        "board_observe", {"node_id": e4_row["child_node_id"]}, idempotency_key="t-obs-child"
    )
    assert child_obs.ok
    packet = child_obs.result["packet"]
    assert packet["state"]["side_to_move"] == "black", "turn alternates after e2e4"
    # …and expandable (the review sequence e2e4 -> c7c5 runs on the child).
    grandchild = session.execute(
        "board_expand",
        {
            "node_id": e4_row["child_node_id"],
            "action_ids": [action_id_v2(e4_row["state_key"], "c7c5", "uci/v1", POLICY_HASH)],
        },
        idempotency_key="t-c5",
    )
    assert grandchild.ok, grandchild.error
    c5_row = grandchild.result["results"][0]
    assert c5_row["depth"] == 2 and e4_row["depth"] == 1, "depth grows along the branch"
    assert c5_row["root_action"] == "e2e4", "root_action is preserved down the branch"
    assert _state_fen(harness, c5_row["state_key"]) == FEN_AFTER_E4_C5
    grand_obs = session.execute(
        "board_observe", {"node_id": c5_row["child_node_id"]}, idempotency_key="t-obs-gc"
    )
    assert grand_obs.ok
    assert grand_obs.result["packet"]["state"]["side_to_move"] == "white"

    # The real root never moved: same packet content as before any expansion.
    root_after = session.execute(
        "board_observe", {"node_id": "node-root"}, idempotency_key="t-obs-root-2"
    )
    assert root_after.result["content_hash"] == root_before.result["content_hash"]
    assert _state_fen(harness, root_before.result["packet"]["state"]["state_key"]) == START_FEN

    # Edges are durable: recoverable from SQLite after the fact.
    database, _engine, _cas = harness
    with CognitionJournal(database).connect() as conn:
        edges = conn.execute(
            text(
                "SELECT parent_node_id, child_node_id, proposed_action FROM search_edges "
                "WHERE search_session_id = 'sess-1' AND legal = 1"
            )
        ).fetchall()
    actions = {row[2] for row in edges}
    assert {"e2e4", "d2d4", "c7c5"} <= actions


def test_expand_resolves_action_from_any_page(harness, tmp_path) -> None:
    """TEST-005/FR-002: an action presented on a LATER packet page stays valid;
    resolution runs over the complete legal set, not page 0."""
    database, engine, cas = harness
    journal = CognitionJournal(database)
    paged_perception = ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
        page_size=5,
    )
    session = DecisionSession.open(
        decision_id="dec-test-0002",
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
        perception=paged_perception,
        cas=cas,
        engine=engine,
    )
    page0 = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="p-obs")
    legal = page0.result["packet"]["legal_actions"]
    assert legal["total_count"] > 5 and legal["next_cursor"] is not None
    page0_ids = {item["action_id"] for item in legal["items"]}
    all_moves = StandardChessEnvironment().legal_actions(ChessGameState()).actions
    late_move = all_moves[10].uci  # beyond page 0 by construction
    late_id = action_id_v2(
        page0.result["packet"]["state"]["state_key"], late_move, "uci/v1", POLICY_HASH
    )
    assert late_id not in page0_ids
    envelope = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [late_id]},
        idempotency_key="p-late",
    )
    assert envelope.ok, envelope.error
    assert envelope.result["results"][0]["uci"] == late_move


def test_expand_batch_with_foreign_action_has_no_partial_effect(harness) -> None:
    """§11.3: one invalid id fails the whole batch before ANY item transitions."""
    session = _open_session(harness)
    database, engine, _cas = harness
    bound_before = CognitionJournal(database).bound_node_ids("dec-test-0001")
    edges_before = _edge_count(engine)
    foreign = "deadbeef" * 8
    envelope = session.execute(
        "board_expand",
        {
            "node_id": "node-root",
            "action_ids": [_legal_action_id(session, "e2e4"), foreign],
        },
        idempotency_key="x-batch",
    )
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "ACTION_STATE_MISMATCH"
    assert CognitionJournal(database).bound_node_ids("dec-test-0001") == bound_before
    assert _edge_count(engine) == edges_before, "no edge may precede the refusal"


def _edge_count(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM search_edges WHERE search_session_id = 'sess-1'")
        ).scalar_one()


def test_expand_reaches_transposition_without_losing_trajectory(harness) -> None:
    """INV-03: Nf3 Nf6 Ng1 Ng8 returns to the root POSITION with a different
    trajectory — a new node bound to the same state, root untouched."""
    session = _open_session(harness)
    node_id = "node-root"
    depth_key = None
    for i, uci in enumerate(["g1f3", "g8f6", "f3g1", "f6g8"]):
        state_key, _ = session._broker._perception.identity_keys(session._broker._states[node_id])
        envelope = session.execute(
            "board_expand",
            {
                "node_id": node_id,
                "action_ids": [action_id_v2(state_key, uci, "uci/v1", POLICY_HASH)],
            },
            idempotency_key=f"tr-{i}",
        )
        assert envelope.ok, envelope.error
        row = envelope.result["results"][0]
        node_id = row["child_node_id"]
        depth_key = row["state_key"]
    assert row["depth"] == 4 and row["terminal"] is False
    assert node_id != "node-root", "transposition must not alias the root node"
    assert _state_fen(harness, depth_key).split(" ")[:4] == START_FEN.split(" ")[:4], (
        "transposition returns to the root position"
    )
    assert session.workspace is not None
    assert session.workspace.stats["transpositions"] >= 1


def test_expand_terminal_node_is_refused(harness) -> None:
    """FR-010/TEST-014: after mate, the terminal node does not transition."""
    session = _open_session(harness)
    node_id = "node-root"
    for i, uci in enumerate(["f2f3", "e7e5", "g2g4", "d8h4"]):
        state_key, _ = session._broker._perception.identity_keys(session._broker._states[node_id])
        envelope = session.execute(
            "board_expand",
            {
                "node_id": node_id,
                "action_ids": [action_id_v2(state_key, uci, "uci/v1", POLICY_HASH)],
            },
            idempotency_key=f"tm-{i}",
        )
        assert envelope.ok, (uci, envelope.error)
        node_id = envelope.result["results"][0]["child_node_id"]
    terminal_obs = session.execute("board_observe", {"node_id": node_id}, idempotency_key="tm-obs")
    assert terminal_obs.result["packet"]["terminal"]["automatic"] is True
    late = session.execute(
        "board_expand",
        {
            "node_id": node_id,
            "action_ids": [_legal_action_id(session, "e2e4")],
        },
        idempotency_key="tm-late",
    )
    assert late.ok is False
    assert late.error is not None
    assert late.error.code == "INVALID_ARGUMENTS"


def test_expand_reports_real_physical_rules_queries(harness) -> None:
    """§42.6 meta: physical_rules_queries reflects kernel work, not a fixed 0."""
    session = _open_session(harness)
    envelope = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [_legal_action_id(session, "e2e4")]},
        idempotency_key="q-e4",
    )
    assert envelope.ok
    assert envelope.meta.physical_rules_queries >= 3, (
        "expansion spends >= 1 legal-set query + 1 validation + 1 transition"
    )
    observe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="q-obs")
    assert observe.meta.physical_rules_queries >= 1


def test_invalid_payload_settles_failed_not_committed(harness, monkeypatch) -> None:
    """TEST-021/ZGW-0101: a tool returning a malformed payload (not raising)
    settles FAILED with OUTPUT_CONTRACT_VIOLATION and exposes no result."""
    session = _open_session(harness)

    def malformed(tool, arguments):
        return {"results": "not-a-list", "content_hash": "packet_content_hash:v2:x"}

    monkeypatch.setattr(session._broker, "_execute_tool", malformed)
    envelope = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [_legal_action_id(session, "e2e4")]},
        idempotency_key="bad-payload",
    )
    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "OUTPUT_CONTRACT_VIOLATION"
    assert envelope.result is None, "an unvalidated payload is never exposed"
    database, engine, _cas = harness
    with engine.connect() as conn:
        status, error_code = conn.execute(
            text(
                "SELECT status, error_code FROM cb_tool_operations "
                "WHERE decision_id = :id AND idempotency_key = 'bad-payload'"
            ),
            {"id": session.decision_id},
        ).fetchone()
        observations = conn.execute(
            text("SELECT COUNT(*) FROM cb_observations WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).scalar_one()
    assert (status, error_code) == ("FAILED", "OUTPUT_CONTRACT_VIOLATION")
    assert observations == 1, "the failure exposure exists (error artifact), not the result"
    # No partial expansion happened either: the malformed body produced no child.
    assert CognitionJournal(database).bound_node_ids("dec-test-0001") == ["node-root"]
