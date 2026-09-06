"""CognitiveBoard CB-M2: conditioned memory tables (PRD §43.2, ZGW-0096).

DDL transcribed from the normative §43.2 target schema: memory items with
immutable revisions, immutable links (frozen once a member snapshot seals),
DRAFT→SEALED snapshots with frozen members, and the seal triggers. Skill-set
tables that depend on CB-M3 stay out — the code above this schema must not
presume future tables (PRD §23.1).

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE cb_memory_items (
        memory_id TEXT NOT NULL PRIMARY KEY,
        logical_memory_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        kind TEXT NOT NULL,
        epistemic_status TEXT NOT NULL CHECK (epistemic_status IN
            ('formal_fact','model_hypothesis','model_assessment','observed_outcome','human_annotation')),
        validity_status TEXT NOT NULL CHECK (validity_status IN
            ('active','needs_review','superseded','contradicted','quarantined')),
        origin_class TEXT NOT NULL CHECK (origin_class IN
            ('rules','endogenous','human','expert_corpus','oracle_informed_offline','evaluation')),
        scope_kind TEXT NOT NULL CHECK (scope_kind IN ('decision','episode','run','corpus','campaign')),
        scope_owner_id TEXT NOT NULL,
        partition_name TEXT NOT NULL CHECK (partition_name IN
            ('train','validation','test','development','unspecified')),
        perspective TEXT NOT NULL CHECK (perspective IN ('white','black','neutral')),
        source_run_id TEXT REFERENCES runs(run_id),
        source_episode_id TEXT REFERENCES episodes(episode_id),
        payload_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        content_hash TEXT NOT NULL,
        source_manifest_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        created_sequence INTEGER NOT NULL CHECK (created_sequence >= 0),
        created_at TEXT NOT NULL,
        UNIQUE(logical_memory_id, revision)
    )
    """,
    "CREATE INDEX cb_memory_scope_idx ON cb_memory_items(scope_kind, scope_owner_id, partition_name)",
    "CREATE INDEX cb_memory_kind_idx ON cb_memory_items(kind, validity_status, created_sequence)",
    """
    CREATE TRIGGER cb_memory_no_update BEFORE UPDATE ON cb_memory_items
    BEGIN SELECT RAISE(ABORT, 'memory revisions are immutable'); END;
    """,
    """
    CREATE TRIGGER cb_memory_no_delete BEFORE DELETE ON cb_memory_items
    BEGIN SELECT RAISE(ABORT, 'memory revisions require audited retention workflow'); END;
    """,
    """
    CREATE TABLE cb_memory_links (
        memory_id TEXT NOT NULL REFERENCES cb_memory_items(memory_id),
        link_kind TEXT NOT NULL CHECK (link_kind IN
            ('state','position','node','root_action','investigation','premise','source_memory')),
        target_key TEXT NOT NULL,
        relation_name TEXT NOT NULL DEFAULT 'about',
        PRIMARY KEY(memory_id, link_kind, target_key, relation_name)
    )
    """,
    "CREATE INDEX cb_memory_link_target_idx ON cb_memory_links(link_kind, target_key)",
    """
    CREATE TRIGGER cb_memory_links_no_update BEFORE UPDATE ON cb_memory_links
    BEGIN SELECT RAISE(ABORT, 'memory links are immutable'); END;
    """,
    """
    CREATE TRIGGER cb_memory_links_no_delete BEFORE DELETE ON cb_memory_links
    BEGIN SELECT RAISE(ABORT, 'memory links require audited retention workflow'); END;
    """,
    """
    CREATE TABLE cb_memory_snapshots (
        snapshot_id TEXT NOT NULL PRIMARY KEY,
        scope_kind TEXT NOT NULL,
        scope_owner_id TEXT NOT NULL,
        partition_name TEXT NOT NULL,
        policy_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('DRAFT','SEALED')),
        manifest_artifact_id TEXT REFERENCES artifacts(artifact_id),
        sealed_at TEXT,
        created_at TEXT NOT NULL,
        CHECK (status <> 'SEALED' OR (manifest_artifact_id IS NOT NULL AND sealed_at IS NOT NULL))
    )
    """,
    """
    CREATE TABLE cb_memory_snapshot_members (
        snapshot_id TEXT NOT NULL REFERENCES cb_memory_snapshots(snapshot_id),
        memory_id TEXT NOT NULL REFERENCES cb_memory_items(memory_id),
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        PRIMARY KEY(snapshot_id, memory_id),
        UNIQUE(snapshot_id, ordinal)
    )
    """,
    """
    CREATE TRIGGER cb_snapshot_members_insert BEFORE INSERT ON cb_memory_snapshot_members
    WHEN (SELECT status FROM cb_memory_snapshots WHERE snapshot_id = NEW.snapshot_id) <> 'DRAFT'
    BEGIN SELECT RAISE(ABORT, 'snapshot is sealed'); END;
    """,
    """
    CREATE TRIGGER cb_snapshot_members_update BEFORE UPDATE ON cb_memory_snapshot_members
    BEGIN SELECT RAISE(ABORT, 'snapshot members cannot be updated'); END;
    """,
    """
    CREATE TRIGGER cb_snapshot_members_delete BEFORE DELETE ON cb_memory_snapshot_members
    WHEN (SELECT status FROM cb_memory_snapshots WHERE snapshot_id = OLD.snapshot_id) <> 'DRAFT'
    BEGIN SELECT RAISE(ABORT, 'snapshot is sealed'); END;
    """,
    """
    CREATE TRIGGER cb_snapshot_no_rewrite BEFORE UPDATE ON cb_memory_snapshots
    WHEN OLD.status = 'SEALED'
    BEGIN SELECT RAISE(ABORT, 'sealed snapshot is immutable'); END;
    """,
    """
    CREATE TRIGGER cb_memory_links_after_seal BEFORE INSERT ON cb_memory_links
    WHEN EXISTS (
     SELECT 1 FROM cb_memory_snapshot_members m
     JOIN cb_memory_snapshots s ON s.snapshot_id = m.snapshot_id
     WHERE m.memory_id = NEW.memory_id AND s.status = 'SEALED'
    )
    BEGIN SELECT RAISE(ABORT, 'sealed memory cannot gain new links'); END;
    """,
]

_DROP_ORDER = [
    "cb_memory_snapshot_members",
    "cb_memory_snapshots",
    "cb_memory_links",
    "cb_memory_items",
]


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)


def downgrade() -> None:
    """Feature rollback. Refuses to drop when memory data exists (PRD §23.3)."""
    bind = op.get_bind()
    item_rows = bind.execute(sa.text("SELECT COUNT(*) FROM cb_memory_items")).scalar()
    if item_rows:
        raise RuntimeError(
            "refusing destructive rollback: cb_memory_items holds "
            f"{item_rows} row(s); archive or clear memory data first"
        )
    for table in _DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    # NOTE: triggers are dropped implicitly with their tables in SQLite.
