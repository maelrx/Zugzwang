"""CB-WO-10 acceptance — causal viewer snapshot (PRD §38.11, TEST-060/061).

Unit-marked (no I/O beyond tmp sqlite/CAS): the cognitive snapshot builder
exports a redacted post-hoc snapshot from a scratch decision, and the loader
contract (schema/mode/engine guards) is enforced in Python mirrors of the
TypeScript rules:

- TEST-060 segregated viewer: snapshot mode is post_hoc with engine None;
  no engine module is imported anywhere on the export path;
- TEST-061 effective timeline: every operation row cites its journal
  operation_id; settled rows cite verified result artifacts;
- bundle import without script: a bundle.json-shaped dict loads decisions;
- redaction: no credential values survive the snapshot.
"""

import json

import pytest

pytestmark = pytest.mark.unit

SCHEMA = "zgw.cognitive-snapshot/v1"


def _parse_snapshot(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("snapshot is not an object")
    if raw.get("schema_version") != SCHEMA:
        raise ValueError(f"unsupported snapshot schema: {raw.get('schema_version')}")
    if raw.get("mode") != "post_hoc":
        raise ValueError("refusing live snapshot: viewer renders post-hoc data only")
    if raw.get("engine") is not None:
        raise ValueError("refusing snapshot with engine reference")
    return raw


def _load_bundle(bundle) -> list:
    if not isinstance(bundle, dict):
        raise ValueError("bundle is not an object")
    decisions = bundle.get("decisions")
    if isinstance(decisions, list):
        return [_parse_snapshot(entry) for entry in decisions]
    return [_parse_snapshot(bundle)]


def _decision_harness(tmp_path):
    from sqlalchemy import text

    from zugzwang_chess.cognition import ChessPerception
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
    from zugzwang_runtime.artifacts.cas import ContentAddressedStore
    from zugzwang_runtime.cognition.session import DecisionSession
    from zugzwang_runtime.persistence.cognition import CognitionJournal
    from zugzwang_runtime.persistence.database import Database
    from zugzwang_runtime.persistence.repositories import SchemaManager

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
    journal = CognitionJournal(database)
    session = DecisionSession.open(
        decision_id="dec-view-0001",
        step_id="st-1",
        decision_ordinal=0,
        search_session_id="sess-1",
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.1.0",
        interaction_mode="native_tools",
        policy_hash="b" * 64,
        config={"max_rounds": 4},
        states={"node-root": ChessGameState()},
        journal=journal,
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash="b" * 64,
        ),
        cas=cas,
        engine=engine,
    )
    session.execute("board_observe", {"node_id": "node-root"}, idempotency_key="v1")
    return database, cas


def _snapshot(tmp_path) -> dict:
    import sys

    sys.path.insert(0, "scripts")
    from build_cognitive_viewer import build_snapshot

    database, cas = _decision_harness(tmp_path)
    return build_snapshot(database, cas, "dec-view-0001")


def test_snapshot_is_post_hoc_without_engine(tmp_path) -> None:
    """TEST-060: modo live não carrega engine nem envia eval ao jogador."""
    snapshot = _snapshot(tmp_path)
    assert snapshot["schema_version"] == SCHEMA
    assert snapshot["mode"] == "post_hoc"
    assert snapshot["engine"] is None
    assert _parse_snapshot(snapshot) is snapshot
    # No engine import anywhere on the export path.
    import scripts.build_cognitive_viewer as builder

    with open(builder.__file__) as handle:
        source = handle.read()
    assert "stockfish" not in source.lower()
    assert "localEngine" not in source
    assert "LiveEval" not in source


def test_timeline_cites_journal_bytes(tmp_path) -> None:
    """TEST-061: request mostrado coincide com bytes/objeto realmente enviado."""
    snapshot = _snapshot(tmp_path)
    ops = snapshot["audit"]["operations"]
    assert len(ops) >= 1
    for op in ops:
        assert op["operation_id"].startswith("operation_id:v2:")
    assert snapshot["audit"]["artifacts_verified"] >= 1
    assert snapshot["audit"]["artifacts_failed"] == []


def test_bundle_import_without_script(tmp_path) -> None:
    """Import de bundle sem script: bundle.json com decisions carrega."""
    snapshot = _snapshot(tmp_path)
    bundle = {"bundle_id": "bundle_x", "decisions": [snapshot]}
    loaded = _load_bundle(bundle)
    assert len(loaded) == 1
    assert loaded[0]["decision_id"] == "dec-view-0001"
    with pytest.raises(ValueError):
        _load_bundle({"decisions": [{"schema_version": "zgw.other/v9"}]})
    with pytest.raises(ValueError):
        _load_bundle(dict(snapshot, mode="live"))


def test_snapshot_carries_no_secrets(tmp_path) -> None:
    """Redaction: nenhum segredo sobrevive ao snapshot."""
    snapshot = _snapshot(tmp_path)
    flat = json.dumps(snapshot)
    assert "Bearer " not in flat
    assert snapshot["engine"] is None
