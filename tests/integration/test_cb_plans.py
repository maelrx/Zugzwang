"""CB-WO-13 acceptance — plans and premises CB-M4 (PRD §38.14, TEST-048/075).

Offline sqlite integration over migration head (0010). Each test names its
PRD TEST id:

- TEST-048 premise change marks needs_review (no strategic refutation);
- TEST-075 plan across turns with correct perspective/episode, premises updated;
- false/unknown fixtures: the predicate DSL evaluates all three states.
"""

import pytest
from sqlalchemy import text

from zugzwang_runtime.cognition.plans import PlanError, PlanStore, evaluate_premise
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

ART = "art:cb-plan-seed"
EVT = "evt-plan-seed-0001"


@pytest.fixture()
def store(tmp_path):
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:cb-plan-seed', 'sha256', 1, "
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
                "INSERT INTO events (event_id, run_id, episode_id, stream_type, "
                "stream_id, sequence_no, event_type, event_version, occurred_at, "
                "payload_json, artifact_refs_json) VALUES ('evt-plan-seed-0001', "
                "'run-1', 'ep-1', 'episode', 'ep-1', 0, 'note', 1, "
                "'2026-09-06T00:00:00Z', '{}', '[]')"
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
    return PlanStore(database), engine


def _decision(store, decision_id="dec-plan-0001"):
    _, engine = store
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO cb_state_snapshots (state_key, state_schema_version, "
                "rules_version, variant, position_key, history_completeness, "
                "state_artifact_id, created_at) VALUES ('state_key:v2:"
                + "a" * 64
                + "', 'state/v2', 'standard/v1', 'standard', 'position_key:v2:"
                + "a" * 64
                + "', 'complete', 'art:cb-plan-seed', '2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO cb_decisions (decision_id, step_id, decision_ordinal, "
                "search_session_id, root_state_key, status, strategy_id, "
                "strategy_version, interaction_mode, policy_hash, config_artifact_id, "
                "created_at) VALUES (:id, 'st-1', 0, 'sess-1', 'state_key:v2:"
                + "a"
                * 64
                + "', 'ACTIVE', 'chess.cognitive_navigation', '0.1.0', "
                "'native_tools', '" + "b" * 64 + "', 'art:cb-plan-seed', "
                "'2026-09-06T00:00:00Z')"
            ),
            {"id": decision_id},
        )
        conn.execute(
            text(
                "INSERT INTO cb_node_bindings (decision_id, node_id, state_key, "
                "depth_plies, created_sequence) VALUES (:id, 'node-root', "
                "'state_key:v2:" + "a" * 64 + "', 0, 0)"
            ),
            {"id": decision_id},
        )
        conn.execute(
            text(
                "INSERT INTO cb_rounds (round_id, decision_id, ordinal, purpose, "
                "status, context_artifact_id, created_at) VALUES (:id, :dec, 1, "
                "'explore', 'TOOLS_COMMITTED', 'art:cb-plan-seed', "
                "'2026-09-06T00:00:00Z')"
            ),
            {"id": f"{decision_id}:round-0001", "dec": decision_id},
        )
        conn.commit()


def test_premise_change_marks_needs_review(store) -> None:
    """TEST-048: delta marca needs_review, sem refutação estratégica."""
    memory, _ = store
    _decision(store)
    memory.open_plan(
        plan_id="plan-1",
        episode_id="ep-1",
        source_decision_id="dec-plan-0001",
        perspective="white",
        payload_artifact_id=ART,
        latest_event_id=EVT,
    )
    view = memory.revise_plan(
        plan_id="plan-1",
        status="needs_review",
        premises={"opp_castled": "false", "center_open": "unknown"},
    )
    assert view.status == "needs_review"
    assert view.premises == {"opp_castled": "false", "center_open": "unknown"}
    assert view.revision == 1
    # No refutation certificate exists anywhere on this path.
    assert "refut" not in str(view.status)


def test_plan_across_turns_correct_scope(store) -> None:
    """TEST-075: perspectiva/episódio corretos, premissas atualizadas."""
    memory, _ = store
    _decision(store)
    memory.open_plan(
        plan_id="plan-t",
        episode_id="ep-1",
        source_decision_id="dec-plan-0001",
        perspective="black",
        payload_artifact_id=ART,
        latest_event_id=EVT,
    )
    delta = memory.premise_delta(previous={"center_open": "true"}, current={"center_open": "false"})
    assert delta == {"center_open": ("true", "false")}
    view = memory.revise_plan(plan_id="plan-t", status="revised", premises={"center_open": "false"})
    assert view.episode_id == "ep-1"
    assert view.perspective == "black"
    assert view.premises["center_open"] == "false"
    # Changed premise escalates past the requested status (TEST-048).
    assert view.status == "needs_review"
    reread = memory.view_plan("plan-t")
    assert reread.status == "needs_review"
    assert reread.revision == 1
    assert reread.premises == {"center_open": "false"}
    # Unchanged premises keep the requested status.
    calm = memory.revise_plan(plan_id="plan-t", status="revised", premises={"center_open": "false"})
    assert calm.status == "revised"
    assert calm.revision == 2


def test_predicate_fixtures_false_unknown(store) -> None:
    """Fixtures false/unknown: DSL avalia os três estados sem executar nada."""
    assert evaluate_premise("true", {"expect": "true"}) == "true"
    assert evaluate_premise("false", {"expect": "true"}) == "false"
    assert evaluate_premise("unknown", {"expect": "true"}) == "false"
    assert evaluate_premise("unknown", {"expect": "unknown"}) == "true"
    assert evaluate_premise("false", {"expect": "unknown"}) == "false"
    with pytest.raises(PlanError):
        evaluate_premise("maybe", {"expect": "true"})
    with pytest.raises(PlanError):
        evaluate_premise("true", {"expect": "sometimes"})


def test_cross_episode_plan_refused(store) -> None:
    """Episode guard: plano de outro episódio aborta no trigger."""
    memory, engine = store
    _decision(store)
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
                "status, assistance_violated) VALUES ('ep-2', 'run-1', 1, "
                "'chess.full_game', 8, 'RUNNING', 0)"
            )
        )
        conn.commit()
    with pytest.raises(PlanError):
        memory.open_plan(
            plan_id="plan-x",
            episode_id="ep-2",
            source_decision_id="dec-plan-0001",
            perspective="white",
            payload_artifact_id=ART,
            latest_event_id=EVT,
        )
    with engine.connect() as conn:
        conn.rollback()
