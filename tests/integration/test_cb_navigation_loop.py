"""CB-WO-07 + ZGW-0101 acceptance — productive navigation loop (PRD §12/§38.8).

Offline, deterministic: the loop calls the typed ``ModelBackend`` (here the
scripted fake) through ``infer`` every round; scripts belong to the fake,
never to the loop. Each test names its PRD TEST id:

- TEST-022 multi-round: observe → expand → grandchild → finalize commits;
- TEST-023 causal feedback: the fake extracts the child_node_id/state_key
  produced in round N out of the round-N TOOL RESULT carried by the round-N+1
  REQUEST, then expands that child — asserted against the request bytes, not
  the final trace, and ``propose_from_transcript`` helpers are not involved;
- TEST-024 wrong-focus finalize rejected (valid at the child, illegal at the
  real root);
- TEST-025 early selection without exhausting the budget;
- TEST-027 json_commands mode: same semantic effect, distinct mode;
- TEST-028 protocol-error ceiling ends the decision;
- TEST-029 exploration never spends the reserved finalization model call;
- TEST-030 exhausted script never falls back to a silent legal move;
- trace/usage come from the effective infer calls (no synthetic records).
"""

import asyncio
import json
from typing import Any

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.domain.cognition import action_id_v2
from zugzwang_core.ports.model import ToolResultPart
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.loop import CognitiveLoop
from zugzwang_runtime.cognition.session import DecisionSession, cas_artifact_loader
from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

POLICY_HASH = "b" * 64


# ---------------------------------------------------------------------------
# fake-side helpers: proposals are derived from the REQUEST the loop sent.
# ---------------------------------------------------------------------------


def _tool_results(messages: list[Any]) -> list[ToolResultPart]:
    return [
        part for message in messages for part in message.parts if isinstance(part, ToolResultPart)
    ]


def _results_named(messages: list[Any], tool: str) -> list[dict[str, Any]]:
    out = []
    for part in _tool_results(messages):
        if part.tool_name == tool and not part.is_error:
            payload = json.loads(part.content)
            if isinstance(payload, dict):
                out.append(payload)
    return out


def propose_observe(_messages: list[Any]) -> dict[str, Any]:
    return {"tool": "board_observe", "arguments": {"node_id": "node-root"}}


def propose_expand_first_action(messages: list[Any]) -> dict[str, Any]:
    """Round 2: expand the first action of the round-1 observation."""
    observations = _results_named(messages, "board_observe")
    assert observations, "round-2 request must carry the round-1 observe result"
    packet = observations[0]["packet"]
    action_id = packet["legal_actions"]["items"][0]["action_id"]
    return {
        "tool": "board_expand",
        "arguments": {"node_id": "node-root", "action_ids": [action_id]},
    }


def propose_expand_real_child(messages: list[Any]) -> dict[str, Any]:
    """Round 3 (the causal probe): pull the child_node_id + state_key produced
    in round 2 OUT OF THE REQUEST and expand THAT child."""
    expansions = _results_named(messages, "board_expand")
    assert expansions, "round-3 request must carry the round-2 expansion result"
    child_node_id = expansions[-1]["results"][0]["child_node_id"]
    child_state_key = expansions[-1]["results"][0]["state_key"]
    reply_id = action_id_v2(child_state_key, "e7e5", "uci/v1", POLICY_HASH)
    return {
        "tool": "board_expand",
        "arguments": {"node_id": child_node_id, "action_ids": [reply_id]},
    }


def propose_finalize_root_action(messages: list[Any]) -> dict[str, Any]:
    """Finalize a root-legal action: by action_id once the round-1 observation
    exists, otherwise by UCI (e2e4 is legal at the start position)."""
    observations = _results_named(messages, "board_observe")
    if not observations:
        return {
            "tool": "board_finalize",
            "arguments": {"node_id": "node-root", "action": "e2e4"},
        }
    packet = observations[0]["packet"]
    action_id = packet["legal_actions"]["items"][0]["action_id"]
    return {
        "tool": "board_finalize",
        "arguments": {"node_id": "node-root", "action_id": action_id},
    }


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------


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


def _open(harness, decision_id="dec-loop-0001", remaining=32, interaction_mode="native_tools"):
    database, engine, cas = harness
    journal = CognitionJournal(database)
    session = DecisionSession.open(
        decision_id=decision_id,
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0",
        interaction_mode=interaction_mode,
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


def _loop(
    session,
    backend: FakeCognitiveBackend,
    harness,
    *,
    interaction_mode: str | None = None,
    **kwargs,
):
    del harness  # the session is the only authorized surface the loop needs
    return CognitiveLoop(
        decision_id=session.decision_id,
        journal=session.journal,
        broker_factory=session.new_broker_for_round,
        backend=backend,
        context_artifact_id=session.round_context_artifact_id,
        max_rounds=kwargs.pop("max_rounds", 4),
        interaction_mode=interaction_mode or session.interaction_mode,
        root_node_id=session.root_node_id,
        **kwargs,
    )


def _run(loop):
    return asyncio.run(loop.run())


def test_multi_round_observe_expand_grandchild_finalize(harness) -> None:
    """TEST-022 + TEST-023: the fake inspects the PRIOR ToolResult inside the
    next request, extracts the runtime-produced child_node_id/state_key, and
    expands THAT child; the loop commits a root-legal action at the end."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            propose_observe,
            propose_expand_first_action,
            propose_expand_real_child,
            propose_finalize_root_action,
        ]
    )
    loop = _loop(session, backend, harness, max_rounds=5)
    result = _run(loop)
    assert result.status == "COMMITTED", result.trace_record
    assert result.selected_action is not None
    assert backend.calls == 4, "finalize in round 4 ends the decision (reserve intact)"
    assert len(backend.seen_requests) == 4

    # Spy: the round-3 REQUEST carried the round-2 expansion datum verbatim.
    round3_results = _results_named(list(backend.seen_requests[2].messages), "board_expand")
    assert round3_results, "round-3 request must contain the round-2 ToolResult"
    child = round3_results[-1]["results"][0]
    assert child["child_node_id"] and child["child_node_id"] != "node-root"
    assert child["depth"] == 1

    # The round-3 proposal expanded the runtime child (see fake probe), so the
    # decision graph now holds the grandchild: recoverable from the journal.
    with session.journal.connect() as conn:
        nodes = conn.execute(
            text(
                "SELECT node_id, depth_plies FROM cb_node_bindings "
                "WHERE decision_id = :id ORDER BY created_sequence"
            ),
            {"id": session.decision_id},
        ).fetchall()
    depths = {row[0]: row[1] for row in nodes}
    assert child["child_node_id"] in depths
    grandchild_depth = max(depths.values())
    assert grandchild_depth == 2, "the causal probe expanded depth-1 child, not the root"

    # Decision row: SELECTED/COMMITTED with source=model.
    with harness[1].connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, selected_action, selection_source FROM cb_decisions "
                "WHERE decision_id = :id"
            ),
            {"id": session.decision_id},
        ).fetchone()
    assert row[0] == "COMMITTED" and row[2] == "model"

    # Real infer evidence: usage comes from the fake's declared usage.
    assert result.calls and all(call.response_ok for call in result.calls)
    assert result.calls[0].usage.input_tokens == 17


def test_causal_feedback_visible_in_request_n_plus_one(harness) -> None:
    """TEST-023 (focused): request N+1 contains round N's result — checked on
    the request bytes the backend actually received."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend(
        [propose_observe, propose_expand_first_action, propose_expand_real_child]
    )
    loop = _loop(session, backend, harness, max_rounds=4)
    _run(loop)
    round2 = backend.seen_requests[1]
    round1_results = _tool_results(list(round2.messages))
    assert round1_results, "round-2 request carries round-1 tool results"
    assert any("packet" in part.content for part in round1_results), (
        "the observation payload itself (not a summary) is in the next request"
    )


def test_finalize_at_wrong_focus_rejected(harness) -> None:
    """TEST-024: action valid at the expanded child but illegal at the ROOT is
    never committed when the finalize names the child as focus."""
    session, _journal = _open(harness)

    def finalize_at_child(messages):
        expansions = _results_named(messages, "board_expand")
        child = expansions[-1]["results"][0]
        # e7e5 is legal at the child (black to move) and NEVER at the root.
        reply_id = action_id_v2(child["state_key"], "e7e5", "uci/v1", POLICY_HASH)
        return {
            "tool": "board_finalize",
            "arguments": {"node_id": child["child_node_id"], "action_id": reply_id},
        }

    backend = FakeCognitiveBackend(
        [propose_observe, propose_expand_first_action, finalize_at_child]
    )
    loop = _loop(session, backend, harness, max_rounds=4)
    result = _run(loop)
    assert result.status == "FAILED"
    assert result.selected_action is None
    assert result.steps[-1].code == "ILLEGAL_ACTION"
    with harness[1].connect() as conn:
        row = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()
    assert row[0] == "FAILED"


def test_early_selection_preserves_budget(harness) -> None:
    """TEST-025: modelo finaliza no round 1 sem consumir o orçamento."""
    session, _journal = _open(harness, remaining=32)
    backend = FakeCognitiveBackend([propose_finalize_root_action])
    loop = _loop(session, backend, harness, max_rounds=4)
    result = _run(loop)
    assert result.status == "COMMITTED"
    assert backend.calls == 1, "early finalize spent a single model call"
    assert session._broker.budget.remaining == 32, "no board operation was charged"


def test_json_commands_same_effect_distinct_mode(harness) -> None:
    """TEST-027: JSON command mode has the same semantic effect as native
    tools, with the interaction mode recorded in every request."""
    session, _journal = _open(harness, interaction_mode="json_commands")
    backend = FakeCognitiveBackend(
        [
            propose_observe,
            propose_expand_first_action,
            propose_finalize_root_action,
        ],
        interaction_mode="json_commands",
    )
    loop = _loop(session, backend, harness, max_rounds=4)
    result = _run(loop)
    assert result.status == "COMMITTED"
    for request in backend.seen_requests:
        assert request.metadata["interaction_mode"] == "json_commands"
        assert request.tools == (), "json mode carries no native tool definitions"


def test_protocol_error_ceiling_ends_decision(harness) -> None:
    """TEST-028: teto de protocol errors encerra a decisão."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            {"tool": "board_observe", "arguments": {"node_id": "node-ghost"}},
            {"tool": "board_observe", "arguments": {"node_id": "node-ghost"}},
        ]
    )
    loop = _loop(session, backend, harness, max_protocol_errors=2, max_rounds=4)
    result = _run(loop)
    assert result.status == "FAILED"
    assert result.protocol_errors == 2
    assert backend.calls == 2
    with harness[1].connect() as conn:
        row = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()
    assert row[0] == "FAILED"


def test_exploration_never_spends_finalize_reserve(harness) -> None:
    """TEST-029: a reserva de finalização é de MODEL calls: com max_rounds=2 e
    reserva 1, o round 2 (reservado) nunca é gasto explorando."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            propose_observe,
            propose_expand_first_action,
            propose_finalize_root_action,
        ]
    )
    loop = _loop(session, backend, harness, max_rounds=2)
    result = _run(loop)
    assert result.status == "FAILED"
    # The reserved round asked the model to finalize (2nd infer) and its
    # exploration proposal was refused before any execution.
    assert backend.calls == 2, "the reserved call is spent ON the finalize attempt"
    assert result.trace_record["failure_code"] == "BUDGET_INSUFFICIENT"
    assert result.selected_action is None
    assert all(step.round_ordinal < 3 for step in result.steps)
    assert not any(step.round_ordinal == 3 for step in result.steps), (
        "no exploration proposal of the reserved round was executed"
    )


def test_failed_finalization_never_falls_back(harness) -> None:
    """TEST-030: script que só explora não escolhe primeiro lance silenciosamente."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend([propose_observe, propose_expand_first_action])
    loop = _loop(session, backend, harness, max_rounds=2)
    result = _run(loop)
    assert result.status == "FAILED"
    assert result.selected_action is None
    with harness[1].connect() as conn:
        row = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()
    assert row[0] == "FAILED"


def test_round_context_carries_exact_request(harness) -> None:
    """FR-020/§22.1: the round context artifact is the exact ModelRequest."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend([propose_observe])
    loop = _loop(session, backend, harness, max_rounds=2)
    _run(loop)
    with session.journal.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ordinal, context_artifact_id FROM cb_rounds "
                "WHERE decision_id = :id AND ordinal >= 2 ORDER BY ordinal"
            ),
            {"id": session.decision_id},
        ).fetchall()
    assert rows, "the loop journaled its own round with the request context"
    ordinal, artifact_id = rows[0]
    _database, _engine, cas = harness
    payload = cas_artifact_loader(cas)(artifact_id)
    assert payload is not None
    stored = json.loads(payload.decode("utf-8"))["request"]
    assert stored["metadata"]["round_ordinal"] == ordinal
    assert stored["messages"][0]["parts"][0]["text"].startswith("You are navigating")


def test_system_prompt_names_real_root_node_id(harness) -> None:
    """Pilot regression: the first request names the decision's REAL root node
    id, so a model that follows the prompt cannot address ROOT/root/0/1 and
    collect NODE_SCOPE_MISMATCH on every observe (real pilot 2026-09-06)."""
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend([propose_observe])
    loop = _loop(session, backend, harness, max_rounds=2)
    assert loop._root_node_id == "node-root"
    _run(loop)
    system_text = backend.seen_requests[0].messages[0].parts[0].text
    assert "'node-root'" in system_text, system_text[:400]
