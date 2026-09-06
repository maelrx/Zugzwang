"""CB-WO-09 acceptance — conditioned memory CB-M2 (PRD §38.10, TEST-042..048/052).

Offline sqlite integration over migration head (0008). Each test names its
PRD TEST id:

- TEST-042 sealed snapshot refuses members/links after seal;
- TEST-043 revision is immutable (new revision row, old untouched);
- TEST-044 eligibility before ranking (out-of-scope similar note refused);
- TEST-045 contaminated engine/eval source refused at write;
- TEST-046 cross-turn memory only within the allowed episode;
- TEST-047 test partition isolated from train/selection;
- TEST-048 premise change marks needs_review (no strategic refutation);
- TEST-052 real frontier (graph-derived actions, notes never decide);
- legacy reader marks unknown fields without inventing origin.
"""

import pytest
import sqlalchemy.exc
from sqlalchemy import text

from zugzwang_runtime.cognition.memory import MemoryError, ScopedMemoryStore
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.integration

ART = "art:cb-memory-seed"
MANIFEST = "art:cb-memory-manifest"


@pytest.fixture()
def store(tmp_path):
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:cb-memory-seed', 'sha256', 1, "
                "'application/json', 'cb/seed.json', '2026-09-06T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
                "relative_path, created_at) VALUES ('art:cb-memory-manifest', 'sha256', 1, "
                "'application/json', 'cb/manifest.json', '2026-09-06T00:00:00Z')"
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
        conn.commit()
    return ScopedMemoryStore(database), engine


def _note(store, **over):
    params = {
        "memory_id": "mem-1-r1",
        "logical_memory_id": "mem-1",
        "revision": 1,
        "kind": "note",
        "epistemic_status": "model_hypothesis",
        "origin_class": "endogenous",
        "scope_kind": "episode",
        "scope_owner_id": "ep-1",
        "partition_name": "development",
        "perspective": "neutral",
        "payload_artifact_id": ART,
        "content_hash": "c" * 64,
        "source_manifest_artifact_id": MANIFEST,
        "source_episode_id": "ep-1",
    }
    params.update(over)
    store[0].write_note(**params)
    return params


def test_sealed_snapshot_refuses_members_and_links(store) -> None:
    """TEST-042: inserir/remover membro após selar é bloqueado."""
    memory, engine = store
    _note(store)
    memory.open_snapshot(
        snapshot_id="snap-1",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="development",
        policy_hash="p" * 64,
    )
    memory.add_member(snapshot_id="snap-1", memory_id="mem-1-r1", ordinal=0)
    memory.seal_snapshot(snapshot_id="snap-1", manifest_artifact_id=MANIFEST)
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        memory.add_member(snapshot_id="snap-1", memory_id="mem-1-r1", ordinal=1)
    with engine.connect() as conn:
        conn.rollback()
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        memory.link(memory_id="mem-1-r1", link_kind="node", target_key="node-x")
    with engine.connect() as conn:
        conn.rollback()
    with pytest.raises(sqlalchemy.exc.IntegrityError), engine.connect() as conn2:
        conn2.execute(text("DELETE FROM cb_memory_snapshot_members WHERE snapshot_id = 'snap-1'"))
    with engine.connect() as conn:
        conn.rollback()


def test_revision_is_immutable(store) -> None:
    """TEST-043: alterar nota produz nova revisão, sem reescrever snapshot."""
    memory, _ = store
    _note(store)
    memory.revise_note(
        memory_id="mem-1-r2",
        logical_memory_id="mem-1",
        revision=2,
        content_hash="d" * 64,
    )
    _, engine = store
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT memory_id, revision, content_hash FROM cb_memory_items "
                "WHERE logical_memory_id = 'mem-1' ORDER BY revision"
            )
        ).fetchall()
        conn.commit()
    assert [(row[0], row[1]) for row in rows] == [("mem-1-r1", 1), ("mem-1-r2", 2)]
    assert rows[0][2] == "c" * 64
    assert rows[1][2] == "d" * 64
    # The old revision row is immutable: a direct UPDATE aborts.
    with pytest.raises(sqlalchemy.exc.IntegrityError), engine.connect() as conn2:
        conn2.execute(
            text("UPDATE cb_memory_items SET content_hash = 'f' * 64 WHERE memory_id = 'mem-1-r1'")
        )
    with engine.connect() as conn:
        conn.rollback()


def test_eligibility_before_ranking(store) -> None:
    """TEST-044: similaridade alta não supera scope inválido."""
    memory, _ = store
    _note(store)
    _note(
        store,
        memory_id="mem-2-r1",
        logical_memory_id="mem-2",
        scope_owner_id="ep-other",
        source_episode_id=None,
    )
    memory.open_snapshot(
        snapshot_id="snap-e",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="development",
        policy_hash="p" * 64,
    )
    memory.add_member(snapshot_id="snap-e", memory_id="mem-1-r1", ordinal=0)
    memory.add_member(snapshot_id="snap-e", memory_id="mem-2-r1", ordinal=1)
    result = memory.recall(snapshot_id="snap-e", scope_kind="episode", scope_owner_id="ep-1")
    assert [item.memory_id for item in result.items] == ["mem-1-r1"]
    assert result.items[0].eligibility_reason == "eligible-scope-partition-validity"


def test_contaminated_source_refused(store) -> None:
    """TEST-045: fonte de engine/eval é negada também na restauração."""
    memory, _ = store
    with pytest.raises(MemoryError) as exc:
        _note(store, origin_class="evaluation")
    assert exc.value.code == "SOURCE_NOT_ALLOWED"
    # Restore path enforces the same gate: a contaminated seed row is refused.
    with pytest.raises(MemoryError) as exc2:
        memory.restore_notes(
            [
                {
                    "memory_id": "mem-x-r1",
                    "logical_memory_id": "mem-x",
                    "payload_artifact_id": "art:cb-memory-seed",
                    "source_manifest_artifact_id": "art:cb-memory-manifest",
                    "origin_class": "evaluation",
                }
            ]
        )
    assert exc2.value.code == "SOURCE_NOT_ALLOWED"
    restored = memory.restore_notes(
        [
            {
                "memory_id": "mem-y-r1",
                "logical_memory_id": "mem-y",
                "payload_artifact_id": "art:cb-memory-seed",
                "source_manifest_artifact_id": "art:cb-memory-manifest",
                "origin_class": "human",
                "scope_owner_id": "ep-1",
            }
        ]
    )
    assert restored == 1


def test_memory_across_turns_scoped_to_episode(store) -> None:
    """TEST-046: nota reaparece só no episódio permitido."""
    memory, _ = store
    _note(store)
    memory.open_snapshot(
        snapshot_id="snap-t",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="development",
        policy_hash="p" * 64,
    )
    memory.add_member(snapshot_id="snap-t", memory_id="mem-1-r1", ordinal=0)
    same = memory.recall(snapshot_id="snap-t", scope_kind="episode", scope_owner_id="ep-1")
    assert len(same.items) == 1
    other = memory.recall(snapshot_id="snap-t", scope_kind="episode", scope_owner_id="ep-2")
    assert other.items == []


def test_test_partition_isolated(store) -> None:
    """TEST-047: dados de test não entram em treino/seleção."""
    memory, _ = store
    _note(store, partition_name="test")
    memory.open_snapshot(
        snapshot_id="snap-p",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="test",
        policy_hash="p" * 64,
    )
    memory.add_member(snapshot_id="snap-p", memory_id="mem-1-r1", ordinal=0)
    result = memory.recall(snapshot_id="snap-p", scope_kind="episode", scope_owner_id="ep-1")
    # Test-scoped snapshot recalls test notes as test-only; a development
    # snapshot never sees them (isolation from train/selection).
    assert [item.memory_id for item in result.items] == ["mem-1-r1"]
    assert result.items[0].eligibility_reason == "eligible-test-scope-only"
    memory.open_snapshot(
        snapshot_id="snap-dev",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="development",
        policy_hash="p" * 64,
    )
    dev = memory.recall(snapshot_id="snap-dev", scope_kind="episode", scope_owner_id="ep-1")
    assert dev.items == [] and dev.evaluative == []


def test_premise_change_marks_needs_review(store) -> None:
    """TEST-048: delta marca needs_review, sem refutação estratégica."""
    memory, _ = store
    _note(store)
    memory.revise_note(
        memory_id="mem-1-r2",
        logical_memory_id="mem-1",
        revision=2,
        premise_changed=True,
        content_hash="e" * 64,
    )
    _, engine = store
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT validity_status FROM cb_memory_items WHERE memory_id = 'mem-1-r2'")
        ).fetchone()
        conn.commit()
    assert row[0] == "needs_review"


def test_real_frontier_uses_graph_not_notes(store) -> None:
    """TEST-052: ações derivadas do grafo; notas avaliativas vão a seção separada."""
    memory, _ = store
    _note(store, memory_id="mem-f-r1", logical_memory_id="mem-f", kind="formal_fact")
    _note(
        store,
        memory_id="mem-a-r1",
        logical_memory_id="mem-a",
        kind="note",
        epistemic_status="model_assessment",
    )
    memory.open_snapshot(
        snapshot_id="snap-f",
        scope_kind="episode",
        scope_owner_id="ep-1",
        partition_name="development",
        policy_hash="p" * 64,
    )
    memory.add_member(snapshot_id="snap-f", memory_id="mem-f-r1", ordinal=0)
    memory.add_member(snapshot_id="snap-f", memory_id="mem-a-r1", ordinal=1)
    result = memory.recall(snapshot_id="snap-f", scope_kind="episode", scope_owner_id="ep-1")
    assert [item.memory_id for item in result.items] == ["mem-f-r1"]
    assert [item.memory_id for item in result.evaluative] == ["mem-a-r1"]
    assert result.evaluative[0].eligibility_reason == "eligible-evaluative-separate-section"
    assert result.items[0].eligibility_reason == "eligible-scope-partition-validity"


def test_legacy_reader_marks_unknowns(store) -> None:
    """Compat: leitor legacy marca desconhecidos sem inventar origem."""
    memory, _ = store
    out = memory.read_legacy_note(
        {"memory_id": "x", "kind": "note", "future_field": 1, "origin": "human"}
    )
    assert out["unknown_fields"] == ["future_field"]
    assert out["origin"] == "human"
    out2 = memory.read_legacy_note({"memory_id": "y"})
    assert out2["origin"] == "unknown-unrecorded"
