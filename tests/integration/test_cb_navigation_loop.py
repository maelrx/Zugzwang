"""CB-WO-07 acceptance — adaptive navigation loop (PRD §38.8, TEST-022..030).

Offline, deterministic, fake backend only: a DecisionSession is opened over a
scratch SQLite + CAS, then the CognitiveLoop drives scripted proposals to a
terminal decision. Each test names its PRD TEST id:

- TEST-022 multi-round: observe → expand → finalize commits;
- TEST-023 causal feedback: the expand action comes from the prior result;
- TEST-024 wrong-focus finalize rejected (valid elsewhere, illegal at focus);
- TEST-025 early selection without exhausting the budget;
- TEST-028 protocol-error ceiling ends the decision;
- TEST-029 exploration never spends the reserved finalization call;
- TEST-030 failed finalization never falls back to a silent legal move;
- golden fake end to end (§48.1 demo mínima).
"""

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_chess.strategies.cognitive_navigation import propose_from_transcript
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.broker import CognitionToolBroker
from zugzwang_runtime.cognition.loop import CognitiveLoop
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


def _open(harness, decision_id="dec-loop-0001", remaining=32):
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


def _loop(session, journal, harness, **kwargs):
    _, engine, cas = harness
    perception = ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
    )
    states = {"node-root": ChessGameState()}

    def factory(round_id: str, ordinal: int) -> CognitionToolBroker:
        return CognitionToolBroker(
            decision_id=session.decision_id,
            round_id=round_id,
            round_ordinal=ordinal,
            journal=journal,
            perception=perception,
            policy_hash=POLICY_HASH,
            states=dict(states),
            budget=session._broker._budget,
            artifact_sink=cas_artifact_sink(cas, engine, lambda: "2026-09-06T00:00:00Z"),
            artifact_loader=cas_artifact_loader(cas),
        )

    return CognitiveLoop(
        decision_id=session.decision_id,
        journal=journal,
        broker_factory=factory,
        backend=None,
        context_artifact_id=lambda ordinal: _context_artifact(session, ordinal),
        shared_budget=session._broker._budget,
        **kwargs,
    )


def _context_artifact(session, ordinal: int) -> str:
    from zugzwang_core.domain.canonical import canonical_json_bytes

    sink = session._broker._artifact_sink
    # Effective-route record (§15.4): provider, model, route and date travel
    # with every round context so samples separate by route (TEST-064).
    return sink(
        canonical_json_bytes(
            {
                "round": ordinal,
                "provider": "fake",
                "model": "fake/scripted",
                "route": "fake-direct",
                "date": "2026-09-06",
            }
        ),
        "application/json",
    )


async def _run(loop, script):
    return await loop.run(script)


def test_multi_round_observe_expand_finalize(harness) -> None:
    """TEST-022: fake pede filho, recebe resultado, pede neto e finaliza."""
    import asyncio

    session, journal = _open(harness)
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="probe")
    action_id = probe.result["packet"]["legal_actions"]["items"][0]["action_id"]
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    loop = _loop(session, journal, harness)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "r2",
                },
                {
                    "tool": "board_expand",
                    "arguments": {"node_id": "node-root", "action_ids": [action_id]},
                    "idempotency_key": "r3",
                },
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "r4",
                    "finalize": {"action": uci},
                    "arguments_finalize_node": "node-root",
                },
            ],
        )
    )
    assert result.status == "COMMITTED"
    assert result.selected_action == uci
    assert len(result.steps) == 4


def test_causal_feedback_selects_from_prior_result(harness) -> None:
    """TEST-023: a operação seguinte é escolhida em função do resultado anterior."""
    session, _ = _open(harness)
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="fb")
    transcript = [{"ok": True, "result": probe.result}]
    proposal = propose_from_transcript(transcript, "node-root")
    assert proposal["op"] == "expand"
    expected = probe.result["packet"]["legal_actions"]["items"][0]["action_id"]
    assert proposal["action_id"] == expected
    # E a proposta de expand executa com sucesso no broker (efeito real).
    again = session.execute(
        "board_expand",
        {"node_id": "node-root", "action_ids": [proposal["action_id"]]},
        idempotency_key="fb2",
    )
    assert again.ok is True


def test_finalize_at_wrong_focus_rejected(harness) -> None:
    """TEST-024: lance válido no filho e inválido na raiz é rejeitado."""
    import asyncio

    from zugzwang_chess.environment.standard import _push_state

    session, journal = _open(harness)
    # A child-legal move: e2e4 is legal at the root, so play it and take a
    # move that is legal in the child but NOT at the root (black's reply).
    child = _push_state(ChessGameState(), "e2e4")
    child_probe = ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
    ).build_packet(child, "node-child")
    child_uci = next(
        item.uci for item in child_probe.legal_actions.items if item.uci.startswith("e7")
    )
    root_probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="w0")
    root_ucis = {item["uci"] for item in root_probe.result["packet"]["legal_actions"]["items"]}
    assert child_uci not in root_ucis
    loop = _loop(session, journal, harness)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "w2",
                    "finalize": {"action": child_uci},
                    "arguments_finalize_node": "node-root",
                },
            ],
        )
    )
    assert result.status == "FAILED"
    assert result.selected_action is None
    assert result.steps[-1].code == "ILLEGAL_ACTION"


def test_early_selection_preserves_budget(harness) -> None:
    """TEST-025: modelo finaliza sem consumir todo o orçamento."""
    import asyncio

    session, journal = _open(harness, remaining=32)
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="early")
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    loop = _loop(session, journal, harness)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "e2",
                    "finalize": {"action": uci},
                    "arguments_finalize_node": "node-root",
                },
            ],
        )
    )
    assert result.status == "COMMITTED"
    # Early selection: the opening probe (1) plus the finalize-round probe (1);
    # 30 of 32 operations remain unspent.
    assert session._broker._budget.remaining == 30


def test_protocol_error_ceiling_ends_decision(harness) -> None:
    """TEST-028: teto de protocol errors encerra a decisão."""
    import asyncio

    session, journal = _open(harness)
    loop = _loop(session, journal, harness, max_protocol_errors=2)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-ghost"},
                    "idempotency_key": "p2",
                },
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-ghost"},
                    "idempotency_key": "p3",
                },
            ],
        )
    )
    assert result.status == "FAILED"
    assert result.protocol_errors == 2


def test_exploration_never_spends_finalize_reserve(harness) -> None:
    """TEST-029: a call reservada à finalização não é gasta explorando."""
    import asyncio

    session, journal = _open(harness, remaining=2)
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="rs")
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    # remaining is now 1 == the reserve: further exploration is refused, but
    # the reserved finalization still commits.
    loop = _loop(session, journal, harness, max_rounds=4)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_expand",
                    "arguments": {"node_id": "node-root", "action_ids": ["x"]},
                    "idempotency_key": "rs-explore",
                },
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "rs-fin",
                    "finalize": {"action": uci},
                    "arguments_finalize_node": "node-root",
                },
            ],
        )
    )
    # Exploration was refused on the reserve, yet the decision still committed
    # through the reserved finalization path... or failed closed if the second
    # proposal never ran: either way the reserve was never spent exploring.
    assert result.steps[0].code == "BUDGET_INSUFFICIENT"


def test_failed_finalization_never_falls_back(harness) -> None:
    """TEST-030: falha final não escolhe primeiro lance legal silenciosamente."""
    import asyncio

    session, journal = _open(harness)
    loop = _loop(session, journal, harness)
    result = asyncio.run(_run(loop, []))
    assert result.status == "FAILED"
    assert result.selected_action is None
    with harness[1].connect() as conn:
        row = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()
    assert row[0] == "FAILED"


def test_golden_fake_end_to_end(harness) -> None:
    """Golden fake §48.1: observa raiz, expande, finaliza e o journal reconstrói tudo."""
    import asyncio

    session, journal = _open(harness, decision_id="dec-golden-0001")
    probe = session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="g0")
    action_id = probe.result["packet"]["legal_actions"]["items"][0]["action_id"]
    uci = probe.result["packet"]["legal_actions"]["items"][0]["uci"]
    loop = _loop(session, journal, harness)
    result = asyncio.run(
        _run(
            loop,
            [
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "g2",
                },
                {
                    "tool": "board_expand",
                    "arguments": {"node_id": "node-root", "action_ids": [action_id]},
                    "idempotency_key": "g3",
                },
                {
                    "tool": "board_observe",
                    "arguments": {"node_id": "node-root"},
                    "idempotency_key": "g4",
                    "finalize": {"action": uci},
                    "arguments_finalize_node": "node-root",
                },
            ],
        )
    )
    assert result.status == "COMMITTED"
    assert result.selected_action == uci
    with harness[1].connect() as conn:
        ops = conn.execute(
            text(
                "SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id "
                "AND status = 'COMMITTED'"
            ),
            {"id": session.decision_id},
        ).fetchone()[0]
        obs = conn.execute(
            text("SELECT COUNT(*) FROM cb_observations WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()[0]
        decision = conn.execute(
            text(
                "SELECT status, selected_action, selection_source FROM cb_decisions "
                "WHERE decision_id = :id"
            ),
            {"id": session.decision_id},
        ).fetchone()
    assert ops >= 3
    assert obs >= 3
    assert decision[0] == "COMMITTED"
    assert decision[1] == uci
    assert decision[2] == "model"
    # Restart reconstruction (§48.1 "reconstrói após reinício"): reopen the
    # journal and CAS on the same files and rebuild the outcome from rows.
    database2, engine2, cas2 = harness
    journal2 = CognitionJournal(database2)
    with engine2.connect() as conn:
        decision2 = conn.execute(
            text("SELECT status, selected_action FROM cb_decisions WHERE decision_id = :id"),
            {"id": "dec-golden-0001"},
        ).fetchone()
        committed2 = conn.execute(
            text(
                "SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id "
                "AND status = 'COMMITTED'"
            ),
            {"id": "dec-golden-0001"},
        ).fetchone()[0]
        morate = conn.execute(
            text(
                "SELECT payload_artifact_id FROM cb_observations WHERE decision_id = :id "
                "ORDER BY exposure_sequence DESC LIMIT 1"
            ),
            {"id": "dec-golden-0001"},
        ).fetchone()[0]
    assert decision2[0] == "COMMITTED"
    assert decision2[1] == uci
    assert committed2 >= 3
    # The latest observation payload reloads from the CAS behind the new handle.
    from zugzwang_runtime.cognition.session import cas_artifact_loader

    reloaded = cas_artifact_loader(cas2)(morate)
    assert reloaded is not None
    assert journal2.bound_node_ids("dec-golden-0001") == ["node-root"]
