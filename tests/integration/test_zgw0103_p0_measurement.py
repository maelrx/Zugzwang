"""ZGW-0103 acceptance — P0 measurement/execution fixes (dossier §17/§18).

Offline, deterministic, against the REAL journal/broker/session stack:

- R2: provider throttling/transport/timeout fail the decision closed under
  their OWN class — never the illegal-action budget (dossier §9.1);
- R6: settled tool operations persist real physical_rules_queries /
  logical_ops / new_nodes (dossier §14: no artificial zeros);
- R7: board_expand ships the child's L0 packet INLINE, so the grandchild
  cycle (candidato → filho → resposta adversária → neto) fits the DEFAULT
  four-round budget that used to close before any neto (dossier §6.3).
"""

import asyncio
from typing import Any

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.domain.cognition import action_id_v2
from zugzwang_core.domain.errors import ProviderThrottlingError, ProviderTimeoutError
from zugzwang_core.ports.model import ToolResultPart
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.loop import CognitiveLoop
from zugzwang_runtime.cognition.navigation import CognitiveNavigationStrategy
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

POLICY_HASH = "b" * 64


# ---------------------------------------------------------------------------
# harness (same shape as test_cb_navigation_loop.py)
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


def _open(harness, decision_id="dec-zgw0103-0001", remaining=32, **session_kwargs):
    database, engine, cas = harness
    journal = CognitionJournal(database)
    session = DecisionSession.open(
        decision_id=decision_id,
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config={},
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
        **session_kwargs,
    )
    return session, journal


def _loop(session, backend, *, max_rounds: int = 4, **kwargs) -> CognitiveLoop:
    return CognitiveLoop(
        decision_id=session.decision_id,
        journal=session.journal,
        broker_factory=session.new_broker_for_round,
        backend=backend,
        context_artifact_id=session.round_context_artifact_id,
        max_rounds=max_rounds,
        interaction_mode=session.interaction_mode,
        root_node_id=session.root_node_id,
        **kwargs,
    )


def _run(loop):
    return asyncio.run(loop.run())


def _tool_results(messages: list[Any]) -> list[ToolResultPart]:
    return [
        part for message in messages for part in message.parts if isinstance(part, ToolResultPart)
    ]


def _results_named(messages: list[Any], tool: str) -> list[dict[str, Any]]:
    out = []
    for part in _tool_results(messages):
        if part.tool_name == tool and not part.is_error:
            payload = json_loads(part.content)
            if isinstance(payload, dict):
                out.append(payload)
    return out


def json_loads(raw: str | bytes) -> Any:
    import json

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


# ---------------------------------------------------------------------------
# ZGX wave 1 mechanisms: inline toggle, harness preload (N0/N1/N2/RICH1)
# ---------------------------------------------------------------------------


def test_inline_child_packages_off_returns_references_only(harness) -> None:
    session, _journal = _open(harness, inline_child_packages=False)
    backend = FakeCognitiveBackend(
        [
            _propose_observe,
            _propose_expand_first_action,
            _propose_finalize,
        ]
    )
    result = _run(_loop(session, backend))
    assert result.status == "COMMITTED"
    expansions = _results_named(list(backend.seen_requests[2].messages), "board_expand")
    row = expansions[-1]["results"][0]
    assert "package" not in row, "N1 control must NOT receive the inline child package"
    assert row["child_node_id"]


def test_preload_root_ships_real_results_in_first_request(harness) -> None:
    """ZGX-02 treatment (N1) + ZGX-03 (N2): the FIRST model request already
    carries the root packet — produced by a REAL journaled broker operation,
    never a synthetic transcript entry."""
    session, journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            _propose_finalize,
        ]
    )
    loop = _loop(session, backend, max_rounds=1, preload_root=True, preload_expand_actions=1)
    result = _run(loop)
    assert result.status == "COMMITTED", result.trace_record
    # the model made exactly ONE call (RICH1-style) and it already saw BOTH
    # the root observation and the expansion result
    assert len(backend.seen_requests) == 1
    first = list(backend.seen_requests[0].messages)
    observes = _results_named(first, "board_observe")
    expands = _results_named(first, "board_expand")
    assert observes and observes[0]["packet"]["state"]["node_id"] == "node-root"
    assert expands and expands[-1]["results"][0]["package"]
    # the preload operations were journaled as REAL tool operations
    with journal.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tool_name FROM cb_tool_operations WHERE decision_id = :id "
                "ORDER BY command_ordinal"
            ),
            {"id": session.decision_id},
        ).fetchall()
    assert [r[0] for r in rows] == ["board_observe", "board_expand", "board_finalize"] or [
        r[0] for r in rows
    ] == ["board_observe", "board_expand"], rows


# ---------------------------------------------------------------------------
# R2: provider failures are their own class (dossier §9.1)
# ---------------------------------------------------------------------------


class _FlakyThenScriptedBackend:
    """Real inference failure injected at a chosen call index."""

    def __init__(self, inner: FakeCognitiveBackend, fail_on_call: int, exc: Exception) -> None:
        self._inner = inner
        self._fail_on_call = fail_on_call
        self._exc = exc
        self.calls = 0

    async def infer(self, request: Any, context: Any) -> Any:
        self.calls += 1
        if self.calls == self._fail_on_call:
            raise self._exc
        return await self._inner.infer(request, context)


@pytest.mark.parametrize(
    ("exc", "expected_class"),
    [
        (ProviderThrottlingError("429", retry_after=1.0), "provider_throttling"),
        (ProviderTimeoutError("deadline"), "provider_timeout_unknown"),
        (ProviderThrottlingError("route saturated"), "provider_throttling"),
    ],
    ids=["throttling", "timeout", "throttling-no-hint"],
)
def test_provider_failure_fails_closed_under_its_own_class(harness, exc, expected_class) -> None:
    session, journal = _open(harness)
    scripted = FakeCognitiveBackend(
        [
            {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
            {"tool": "board_finalize", "arguments": {"node_id": "node-root", "action": "e2e4"}},
        ]
    )
    backend = _FlakyThenScriptedBackend(scripted, fail_on_call=2, exc=exc)
    result = _run(_loop(session, backend))
    assert result.status == "FAILED"
    assert result.failure_class == expected_class
    assert result.trace_record["failure_class"] == expected_class
    assert result.trace_record["failure_code"].startswith("ZGZ-PROVIDER_")
    # The decision journal records FAILED, and NO illegal-action marker was
    # produced: the failure is a provider event, not an action-policy event.
    with journal.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchone()
    assert status is not None and status[0] == "FAILED"
    illegal_markers = [step for step in result.steps if step.code == "ILLEGAL_ACTION"]
    assert illegal_markers == []

    # navigation surfaces the provider verdict the coordinator keys on.
    trace = CognitiveNavigationStrategy()._trace_from(result, context=None)
    assert any(verdict.kind == "provider_error" for verdict in trace.verdicts)
    assert trace.termination_reason == expected_class
    assert trace.final_action is None


# ---------------------------------------------------------------------------
# R6: physical counters persist from the execution point (dossier §14)
# ---------------------------------------------------------------------------


def test_settled_operations_carry_real_physical_counters(harness) -> None:
    session, journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
            {"tool": "board_finalize", "arguments": {"node_id": "node-root", "action": "e2e4"}},
        ]
    )
    result = _run(_loop(session, backend))
    assert result.status == "COMMITTED"
    with journal.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tool_name, physical_rules_queries, logical_ops, new_nodes "
                "FROM cb_tool_operations WHERE decision_id = :id ORDER BY command_ordinal"
            ),
            {"id": session.decision_id},
        ).fetchall()
    counters = {row[0]: (row[1], row[2], row[3]) for row in rows}
    assert "board_observe" in counters
    observe_physical, observe_logical, observe_new = counters["board_observe"]
    # A packet build IS a physical legal-set query: never an invented zero.
    assert observe_physical >= 1
    assert observe_logical >= 1
    assert observe_new == 0


# ---------------------------------------------------------------------------
# R7: inline child package + the grandchild cycle inside the default budget
# ---------------------------------------------------------------------------


def _propose_observe(_messages: list[Any]) -> dict[str, Any]:
    return {"tool": "board_observe", "arguments": {"node_id": "node-root"}}


def _propose_expand_first_action(messages: list[Any]) -> dict[str, Any]:
    observations = _results_named(messages, "board_observe")
    assert observations, "round-2 request must carry the round-1 observe result"
    action_id = observations[0]["packet"]["legal_actions"]["items"][0]["action_id"]
    return {
        "tool": "board_expand",
        "arguments": {"node_id": "node-root", "action_ids": [action_id]},
    }


def _propose_expand_child_reply(messages: list[Any]) -> dict[str, Any]:
    """The adversarial-reply probe: expand the CHILD produced in round 2,
    answering it with e7e5 — a grandchild at relative depth two."""
    expansions = _results_named(messages, "board_expand")
    assert expansions, "round-3 request must carry the round-2 expansion result"
    child = expansions[-1]["results"][0]
    reply_id = action_id_v2(child["state_key"], "e7e5", "uci/v1", POLICY_HASH)
    return {
        "tool": "board_expand",
        "arguments": {"node_id": child["child_node_id"], "action_ids": [reply_id]},
    }


def _propose_finalize(messages: list[Any]) -> dict[str, Any]:
    observations = _results_named(messages, "board_observe")
    assert observations
    action_id = observations[0]["packet"]["legal_actions"]["items"][0]["action_id"]
    return {
        "tool": "board_finalize",
        "arguments": {"node_id": "node-root", "action_id": action_id},
    }


def test_expand_ships_child_package_inline(harness) -> None:
    session, _journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            _propose_observe,
            _propose_expand_first_action,
            _propose_finalize,
        ]
    )
    result = _run(_loop(session, backend))
    assert result.status == "COMMITTED"
    # call 3 (finalize) carries the round-2 expansion result in its transcript
    round2 = _results_named(list(backend.seen_requests[2].messages), "board_expand")
    child = round2[-1]["results"][0]
    # The child's authorized L0 packet travels with the expansion result.
    package = child["package"]
    assert package["state"]["node_id"] == child["child_node_id"]
    assert package["representation"]["fen"], "child package must carry the position"
    assert package["legal_actions"]["items"], "child package must carry its legal set"
    assert child["package_content_hash"]


def test_grandchild_cycle_fits_default_four_round_budget(harness) -> None:
    """Dossier §6.3: observe → expand(root) → expand(child reply) → finalize.
    With inline child packages this whole cycle fits max_rounds=4 — the old
    package-by-observe flow needed the fourth call just to LOOK at a child."""
    session, journal = _open(harness)
    backend = FakeCognitiveBackend(
        [
            _propose_observe,
            _propose_expand_first_action,
            _propose_expand_child_reply,
            _propose_finalize,
        ]
    )
    result = _run(_loop(session, backend, max_rounds=4))
    assert result.status == "COMMITTED", result.trace_record
    with journal.connect() as conn:
        rows = conn.execute(
            text("SELECT depth_plies FROM cb_node_bindings WHERE decision_id = :id"),
            {"id": session.decision_id},
        ).fetchall()
    depths = sorted(row[0] for row in rows)
    assert depths == [0, 1, 2], "root, child and GRANDCHILD must be bound"
