"""ZGW-0101 — memory/skills/plans reach the EFFECTIVE request (T5b).

Proves the binding, not the store: an eligible note or an activated skill
appears in the ModelRequest the loop actually sent (inspected on the fake
backend's seen_requests), and a plan is revised from the real round results.
Memory OFF (no binding) is observably absent — never an empty placeholder.
"""

import asyncio

import pytest
from sqlalchemy import text

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.ports.strategy import DecisionContext
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.memory import ScopedMemoryStore
from zugzwang_runtime.cognition.navigation import CognitiveNavigationStrategy
from zugzwang_runtime.cognition.plans import PlanStore
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.cognition.skills import SkillRegistry
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
            "INSERT INTO events (event_id, run_id, episode_id, stream_type, "
            "stream_id, sequence_no, event_type, event_version, occurred_at, "
            "payload_json, artifact_refs_json) VALUES ('evt:1', 'run-1', 'ep-1', "
            "'episode', 'ep-1', 0, 'note', 1, '2026-09-06T00:00:00Z', '{}', '[]')",
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


def _open(harness, decision_id="dec-ctx-0001", remaining=64, model_calls=8):
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
        max_model_calls=model_calls,
    )
    return session, journal, database, engine, cas


def test_eligible_memory_appears_in_effective_request(harness) -> None:
    """One ELIGIBLE note → its logical id is in the model-bound request; OFF → absent."""
    session, _journal, database, _engine, _cas = _open(harness)
    store = ScopedMemoryStore(database)
    store.write_note(
        memory_id="mem-w-r1",
        logical_memory_id="mem-w",
        revision=1,
        kind="note",
        epistemic_status="formal_fact",
        origin_class="human",
        scope_kind="episode",
        scope_owner_id="",
        partition_name="development",
        perspective="neutral",
        payload_artifact_id="art:seed",
        source_manifest_artifact_id="art:seed",
        content_hash="c" * 64,
    )
    store.open_snapshot(
        snapshot_id="snap-ctx",
        scope_kind="episode",
        scope_owner_id="",
        partition_name="development",
        policy_hash="p" * 64,
    )
    store.add_member(snapshot_id="snap-ctx", memory_id="mem-w-r1", ordinal=0)
    store.seal_snapshot(snapshot_id="snap-ctx", manifest_artifact_id="art:seed")
    session.memory_store = store
    with session.journal.connect() as conn:
        conn.execute(
            text("UPDATE cb_decisions SET memory_snapshot_id = 'snap-ctx' WHERE decision_id = :id"),
            {"id": session.decision_id},
        )
        conn.commit()

    backend = FakeCognitiveBackend(
        [
            lambda messages: {
                "tool": "board_finalize",
                "arguments": {"node_id": "node-root", "action": "e2e4"},
            }
        ]
    )
    strategy = CognitiveNavigationStrategy(max_rounds=3)
    from zugzwang_core.ports.model import ModelRef

    trace = asyncio.run(
        strategy.decide(
            {"node_id": "node-root"},
            DecisionContext(
                run_id="run-1",
                episode_id="ep-1",
                step_id="st-1",
                model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
                backend=backend,
                tools={},
                seed=7,
                decision_session=session,
            ),
        )
    )
    assert trace.final_action == "e2e4"
    system_text = backend.seen_requests[0].messages[0].parts[0].text
    assert "ELIGIBLE MEMORY" in system_text, "the bound note shapes the request"
    assert "mem-w" in system_text
    assert "snap-ctx" in system_text, "the FROZEN snapshot id is named"

    # OFF branch: no binding → no memory section at all.
    with session.journal.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-2','run-1','alg','0.1','ns',"
                "'node-root-2','{}','{}','RUNNING','2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
                "trajectory_key, state_ref, depth, terminal, created_by, status) "
                "VALUES ('node-root-2','sess-2','pos:root','traj:root','cas://root',"
                "0,0,'perception','OPEN')"
            )
        )
        conn.commit()
    database, engine, cas = harness
    journal2 = CognitionJournal(database)
    session2 = DecisionSession.open(
        decision_id="dec-ctx-0002",
        step_id="st-1",
        decision_ordinal=1,
        search_session_id="sess-2",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config={},
        states={"node-root-2": ChessGameState()},
        journal=journal2,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        cas=cas,
        engine=engine,
        remaining_tool_operations=32,
        max_model_calls=4,
    )
    session2.memory_store = store
    backend2 = FakeCognitiveBackend(
        [
            lambda messages: {
                "tool": "board_finalize",
                "arguments": {"node_id": "node-root", "action": "e2e4"},
            }
        ]
    )
    asyncio.run(
        strategy.decide(
            {"node_id": "node-root"},
            DecisionContext(
                run_id="run-1",
                episode_id="ep-1",
                step_id="st-1",
                model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
                backend=backend2,
                tools={},
                seed=7,
                decision_session=session2,
            ),
        )
    )
    assert "ELIGIBLE MEMORY" not in backend2.seen_requests[0].messages[0].parts[0].text


def test_activated_skill_is_named_in_effective_request(harness) -> None:
    """A sealed, bound skill set surfaces in the request through the loop path."""
    session, _journal, database, _engine, _cas = _open(harness)
    registry = SkillRegistry(database)
    registry.propose(
        skill_version_id="sv-ctx",
        skill_id="openings",
        version="1",
        payload_artifact_id="art:seed",
        provenance_artifact_id="art:seed",
        content_hash="d" * 64,
        origin_class="human",
    )
    approved_id = registry.approve(skill_version_id="sv-ctx", approval_artifact_id="art:seed")
    registry.open_set(skill_set_id="set-ctx", policy_hash="p" * 64)
    registry.add_member(skill_set_id="set-ctx", skill_version_id=approved_id, ordinal=0)
    registry.seal_set(skill_set_id="set-ctx", manifest_artifact_id="art:seed")
    session.skill_registry = registry
    registry.bind_decision(decision_id=session.decision_id, skill_set_id="set-ctx")

    backend = FakeCognitiveBackend(
        [
            lambda messages: {
                "tool": "board_finalize",
                "arguments": {"node_id": "node-root", "action": "e2e4"},
            }
        ]
    )
    strategy = CognitiveNavigationStrategy(max_rounds=3)
    from zugzwang_core.ports.model import ModelRef

    trace = asyncio.run(
        strategy.decide(
            {"node_id": "node-root"},
            DecisionContext(
                run_id="run-1",
                episode_id="ep-1",
                step_id="st-1",
                model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
                backend=backend,
                tools={},
                seed=7,
                config={"cognitive": {"skill_id": "openings"}},
                decision_session=session,
            ),
        )
    )
    assert trace.final_action == "e2e4"
    system_text = backend.seen_requests[0].messages[0].parts[0].text
    assert "ACTIVE SKILL openings v1" in system_text
    assert "set-ctx" in system_text


def test_plan_revised_from_real_round_results(harness) -> None:
    """A mate-in-one branch commits a terminal child; the plan flips to
    needs_review through the productive round-feedback hook."""
    session, _journal, _db, _engine, _cas = _open(harness)
    store = PlanStore(_db)
    store.open_plan(
        plan_id="plan-ctx",
        episode_id="ep-1",
        source_decision_id=session.decision_id,
        perspective="white",
        payload_artifact_id="art:seed",
        latest_event_id="evt:1",
    )
    store.revise_plan(
        plan_id="plan-ctx",
        status="active",
        premises={"position_terminal": "false"},
    )
    session.plan_store = store

    async def mate_branch():
        # Route through the productive session so the round feedback sees a
        # real terminal expansion: f3 e5 g4 Qh4# needs the full line.
        from zugzwang_core.ports.model import ModelRef

        backend = FakeCognitiveBackend(
            [
                lambda messages: {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
            ]
            + [
                lambda messages, _uci=uci: {
                    "tool": "board_expand",
                    "arguments": {
                        "node_id": node_of(messages, _uci),
                        "action_ids": [aid_of(messages, _uci)],
                    },
                }
                for uci in ("f2f3", "e7e5", "g2g4")
            ]
            + [
                lambda messages: make_mate_final(messages),
                lambda messages: {
                    "tool": "board_finalize",
                    "arguments": {"node_id": "node-root", "action": "e2e4"},
                },
            ]
        )

        def make_mate_final(messages):
            # d8h4# is the terminal reply: commit the expansion, then propose
            # the finalize in the FOLLOWING round (a finalize proposal cannot
            # ride in the same round as its own expansion result).
            exps = [p for p in _parts(messages) if p[0] == "board_expand"]
            if len(exps) < 3:
                return {
                    "tool": "board_observe",
                    "arguments": {"node_id": session.root_node_id or "node-root"},
                }
            return {
                "tool": "board_expand",
                "arguments": {
                    "node_id": node_of(messages, "d8h4"),
                    "action_ids": [aid_of(messages, "d8h4")],
                },
            }

        def node_of(messages, uci):
            expansions = [p for p in _parts(messages) if p[0] == "board_expand"]
            if expansions:
                return expansions[-1][1]["results"][0]["child_node_id"]
            return session.root_node_id or "node-root"

        def aid_of(messages, uci):

            expansions = [p for p in _parts(messages) if p[0] == "board_expand"]
            if expansions:
                key = expansions[-1][1]["results"][0]["state_key"]
            else:
                observes = [p for p in _parts(messages) if p[0] == "board_observe"]
                key = observes[0][1]["packet"]["state"]["state_key"]
            from zugzwang_core.domain.cognition import action_id_v2

            return action_id_v2(key, uci, "uci/v1", POLICY_HASH)

        def _parts(messages):
            import json as _json

            out = []
            for message in messages:
                for part in message.parts:
                    if getattr(part, "type", "") == "tool_result":
                        out.append((part.tool_name, _json.loads(part.content)))
            return out

        strategy = CognitiveNavigationStrategy(max_rounds=9)
        return await strategy.decide(
            {"node_id": "node-root"},
            DecisionContext(
                run_id="run-1",
                episode_id="ep-1",
                step_id="st-1",
                model=ModelRef(backend="fake.cognitive", provider="fake", model="scripted"),
                backend=backend,
                tools={},
                seed=7,
                config={"cognitive": {"plan_id": "plan-ctx"}},
                decision_session=session,
            ),
        )

    trace = asyncio.run(mate_branch())
    assert trace.final_action == "e2e4", trace.selection_rationale
    assert trace.selection_rationale["protocol_errors"] == 0
    view = store.view_plan("plan-ctx")
    assert view.status == "needs_review", "the terminal child flipped the premise"
    assert view.premises.get("position_terminal") == "true"
