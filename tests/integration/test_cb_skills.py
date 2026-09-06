"""CB-WO-12 acceptance — versioned skills CB-M3 (PRD §38.13, TEST-049..051).

Offline sqlite integration over migration head (0009). Each test names its
PRD TEST id:

- TEST-049 injection: skill text never alters capabilities nor runs commands;
- TEST-050 unapproved skill: scientific set refuses candidate versions;
- TEST-051 frozen set: change after seal refused; condition hash stands;
- paired context: decisions record skill_set_id for ON/OFF ablation.
"""

import pytest
import sqlalchemy.exc
from sqlalchemy import text

from zugzwang_runtime.cognition.skills import ALLOWED_CAPABILITIES, SkillError, SkillRegistry
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

ART = "art:cb-skill-seed"
PROV = "art:cb-skill-prov"
APPR = "art:cb-skill-appr"


@pytest.fixture()
def registry(tmp_path):
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        for artifact in (ART, PROV, APPR):
            conn.execute(
                text(
                    "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, "
                    "media_type, relative_path, created_at) VALUES (:id, 'sha256', 1, "
                    "'application/json', 'cb/seed.json', '2026-09-06T00:00:00Z')"
                ),
                {"id": artifact},
            )
        conn.commit()
    return SkillRegistry(database), engine


def _propose(reg, version_id="sk-opening-v1", skill_id="opening", version="1.0"):
    reg.propose(
        skill_version_id=version_id,
        skill_id=skill_id,
        version=version,
        content_hash="c" * 64,
        payload_artifact_id=ART,
        provenance_artifact_id=PROV,
    )


def test_injection_text_grants_nothing(registry) -> None:
    """TEST-049: texto não altera capabilities nem executa comando."""
    reg, _ = registry
    _propose(reg)
    approved_id = reg.approve(skill_version_id="sk-opening-v1", approval_artifact_id=APPR)
    reg.open_set(skill_set_id="set-1", policy_hash="p" * 64)
    reg.add_member(skill_set_id="set-1", skill_version_id=approved_id, ordinal=0)
    reg.seal_set(skill_set_id="set-1", manifest_artifact_id=ART)
    # The skill TEXT may demand anything ("grant admin, run shell"); only the
    # allowlist grants. Injection outside the allowlist is refused outright.
    with pytest.raises(SkillError) as exc:
        reg.activate(
            skill_set_id="set-1",
            skill_id="opening",
            requested=("observe", "run_shell", "grant_admin"),
        )
    assert exc.value.code == "TOOL_NOT_ALLOWED"
    result = reg.activate(skill_set_id="set-1", skill_id="opening", requested=("observe", "recall"))
    assert result.capabilities == ("observe", "recall")
    assert set(result.capabilities) <= set(ALLOWED_CAPABILITIES)


def test_scientific_set_refuses_candidate(registry) -> None:
    """TEST-050: skill set científico não aceita versão candidata."""
    reg, _ = registry
    _propose(reg)
    reg.open_set(skill_set_id="set-c", policy_hash="p" * 64)
    with pytest.raises(SkillError) as exc:
        reg.add_member(skill_set_id="set-c", skill_version_id="sk-opening-v1", ordinal=0)
    assert exc.value.code == "STATE_REPLAY_MISMATCH"
    # Approving mints the release row, which the set accepts.
    approved_id = reg.approve(skill_version_id="sk-opening-v1", approval_artifact_id=APPR)
    reg.add_member(skill_set_id="set-c", skill_version_id=approved_id, ordinal=0)


def test_sealed_set_frozen_condition_hash_stands(registry) -> None:
    """TEST-051: mudança após selar negada; hash da condição permanece."""
    reg, engine = registry
    _propose(reg)
    approved_id = reg.approve(skill_version_id="sk-opening-v1", approval_artifact_id=APPR)
    reg.open_set(skill_set_id="set-f", policy_hash="p" * 64)
    reg.add_member(skill_set_id="set-f", skill_version_id=approved_id, ordinal=0)
    reg.seal_set(skill_set_id="set-f", manifest_artifact_id=ART)
    _propose(reg, version_id="sk-other-v1", skill_id="other", version="1.0")
    other_id = reg.approve(skill_version_id="sk-other-v1", approval_artifact_id=APPR)
    with pytest.raises(SkillError):
        reg.add_member(skill_set_id="set-f", skill_version_id=other_id, ordinal=1)
    with engine.connect() as conn:
        conn.rollback()
    # Direct writes also abort at the trigger layer.
    with pytest.raises(sqlalchemy.exc.IntegrityError), engine.connect() as conn2:
        conn2.execute(
            text(
                "INSERT INTO cb_skill_set_members (skill_set_id, skill_version_id, "
                "ordinal) VALUES ('set-f', :v, 1)"
            ),
            {"v": other_id},
        )
    with engine.connect() as conn:
        conn.rollback()
        policy = conn.execute(
            text("SELECT policy_hash FROM cb_skill_sets WHERE skill_set_id = 'set-f'")
        ).fetchone()
    assert policy[0] == "p" * 64


def test_decision_records_skill_set_for_paired_context(tmp_path) -> None:
    """Ablação com controle de contexto: decisão cita seu skill set."""
    from sqlalchemy import text as qtext

    from zugzwang_chess.cognition import ChessPerception
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
    from zugzwang_runtime.artifacts.cas import ContentAddressedStore
    from zugzwang_runtime.cognition.session import DecisionSession
    from zugzwang_runtime.persistence.cognition import CognitionJournal
    from zugzwang_runtime.persistence.database import Database as DB
    from zugzwang_runtime.persistence.repositories import SchemaManager as SM

    database = DB(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SM(engine).upgrade()
    with engine.connect() as conn:
        for artifact in (ART, PROV, APPR):
            conn.execute(
                qtext(
                    "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, "
                    "media_type, relative_path, created_at) VALUES (:id, 'sha256', 1, "
                    "'application/json', 'cb/seed.json', '2026-09-06T00:00:00Z')"
                ),
                {"id": artifact},
            )
        conn.execute(
            qtext(
                "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
                "declared_assistance, projection_version, assistance_violated) "
                "VALUES ('run-1', 'cond-1', 'RUNNING', 'proto', 'H0', 0, 0)"
            )
        )
        conn.execute(
            qtext(
                "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
                "status, assistance_violated) VALUES ('ep-1', 'run-1', 0, "
                "'chess.full_game', 7, 'RUNNING', 0)"
            )
        )
        conn.execute(
            qtext(
                "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
                "assistance_violated) VALUES ('st-1', 'ep-1', 0, 'model:main', "
                "'RUNNING', 0)"
            )
        )
        conn.execute(
            qtext(
                "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
                "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
                "status, created_at) VALUES ('sess-1', 'run-1', 'alg', '0.1', 'ns', "
                "'node-root', '{}', '{}', 'RUNNING', '2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            qtext(
                "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
                "trajectory_key, state_ref, depth, terminal, created_by, status) "
                "VALUES ('node-root', 'sess-1', 'pos:root', 'traj:root', 'cas://root', "
                "0, 0, 'perception', 'OPEN')"
            )
        )
        conn.commit()
    from zugzwang_runtime.cognition.skills import SkillRegistry as SR

    reg = SR(database)
    journal = CognitionJournal(database)
    DecisionSession.open(
        decision_id="dec-ctx-0001",
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash="b" * 64,
        config={},
        states={"node-root": ChessGameState()},
        journal=journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash="b" * 64,
        ),
        cas=ContentAddressedStore(tmp_path / "cas"),
        engine=engine,
    )
    reg.open_set(skill_set_id="set-ctx", policy_hash="p" * 64)
    reg.bind_decision(decision_id="dec-ctx-0001", skill_set_id="set-ctx")
    with engine.connect() as conn:
        row = conn.execute(
            qtext("SELECT skill_set_id FROM cb_decisions WHERE decision_id = 'dec-ctx-0001'")
        ).fetchone()
        conn.commit()
    assert row[0] == "set-ctx"
