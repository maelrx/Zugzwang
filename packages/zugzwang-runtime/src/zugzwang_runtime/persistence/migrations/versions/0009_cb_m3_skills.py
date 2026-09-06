"""CognitiveBoard CB-M3: skill registry tables (PRD §43.2, ZGW-0099).

DDL transcribed from the normative §43.2 target schema: immutable skill
versions with the CANDIDATE→APPROVED/REJECTED pipeline, DRAFT→SEALED skill
sets with approved-only members, and the decision bindings (memory snapshot
and skill set) that the intermediate CB-M1 subset intentionally left out.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE cb_skill_versions (
        skill_version_id TEXT NOT NULL PRIMARY KEY,
        skill_id TEXT NOT NULL,
        version TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        payload_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        provenance_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        approval_artifact_id TEXT REFERENCES artifacts(artifact_id),
        origin_class TEXT NOT NULL CHECK (origin_class IN
            ('proposed_procedure','human','endogenous','oracle_informed_offline')),
        status TEXT NOT NULL CHECK (status IN ('CANDIDATE','APPROVED','REJECTED')),
        created_at TEXT NOT NULL,
        UNIQUE(skill_id, version),
        CHECK (status <> 'APPROVED' OR approval_artifact_id IS NOT NULL)
    )
    """,
    """
    CREATE TRIGGER cb_skill_version_no_update BEFORE UPDATE ON cb_skill_versions
    BEGIN SELECT RAISE(ABORT, 'skill versions are immutable; approval creates a release version'); END;
    """,
    """
    CREATE TRIGGER cb_skill_version_no_delete BEFORE DELETE ON cb_skill_versions
    BEGIN SELECT RAISE(ABORT, 'skill versions require audited retention workflow'); END;
    """,
    """
    CREATE TABLE cb_skill_sets (
        skill_set_id TEXT NOT NULL PRIMARY KEY,
        policy_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('DRAFT','SEALED')),
        manifest_artifact_id TEXT REFERENCES artifacts(artifact_id),
        created_at TEXT NOT NULL,
        sealed_at TEXT,
        CHECK (status <> 'SEALED' OR (manifest_artifact_id IS NOT NULL AND sealed_at IS NOT NULL))
    )
    """,
    """
    CREATE TABLE cb_skill_set_members (
        skill_set_id TEXT NOT NULL REFERENCES cb_skill_sets(skill_set_id),
        skill_version_id TEXT NOT NULL REFERENCES cb_skill_versions(skill_version_id),
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        PRIMARY KEY(skill_set_id, skill_version_id),
        UNIQUE(skill_set_id, ordinal)
    )
    """,
    """
    CREATE TRIGGER cb_skill_member_insert BEFORE INSERT ON cb_skill_set_members
    WHEN (SELECT status FROM cb_skill_sets WHERE skill_set_id = NEW.skill_set_id) <> 'DRAFT'
     OR (SELECT status FROM cb_skill_versions WHERE skill_version_id = NEW.skill_version_id) <> 'APPROVED'
    BEGIN SELECT RAISE(ABORT, 'skill set sealed or skill not approved'); END;
    """,
    """
    CREATE TRIGGER cb_skill_member_update BEFORE UPDATE ON cb_skill_set_members
    BEGIN SELECT RAISE(ABORT, 'skill set members cannot be updated'); END;
    """,
    """
    CREATE TRIGGER cb_skill_member_delete BEFORE DELETE ON cb_skill_set_members
    WHEN (SELECT status FROM cb_skill_sets WHERE skill_set_id = OLD.skill_set_id) <> 'DRAFT'
    BEGIN SELECT RAISE(ABORT, 'skill set is sealed'); END;
    """,
    """
    CREATE TRIGGER cb_skill_set_no_rewrite BEFORE UPDATE ON cb_skill_sets
    WHEN OLD.status = 'SEALED'
    BEGIN SELECT RAISE(ABORT, 'sealed skill set is immutable'); END;
    """,
    "ALTER TABLE cb_decisions ADD COLUMN memory_snapshot_id TEXT REFERENCES cb_memory_snapshots(snapshot_id)",
    "ALTER TABLE cb_decisions ADD COLUMN skill_set_id TEXT REFERENCES cb_skill_sets(skill_set_id)",
    """
    CREATE TRIGGER cb_decision_snapshot_insert BEFORE INSERT ON cb_decisions
    WHEN (NEW.memory_snapshot_id IS NOT NULL AND
         (SELECT status FROM cb_memory_snapshots WHERE snapshot_id = NEW.memory_snapshot_id) <> 'SEALED')
     OR (NEW.skill_set_id IS NOT NULL AND
         (SELECT status FROM cb_skill_sets WHERE skill_set_id = NEW.skill_set_id) <> 'SEALED')
    BEGIN SELECT RAISE(ABORT, 'decision requires sealed snapshots'); END;
    """,
    """
    CREATE TRIGGER cb_decision_snapshot_fixed BEFORE UPDATE ON cb_decisions
    WHEN (
      (NEW.memory_snapshot_id <> OLD.memory_snapshot_id
       OR ((NEW.memory_snapshot_id IS NULL) <> (OLD.memory_snapshot_id IS NULL)))
      AND OLD.memory_snapshot_id IS NOT NULL
     OR (NEW.skill_set_id <> OLD.skill_set_id
       OR ((NEW.skill_set_id IS NULL) <> (OLD.skill_set_id IS NULL)))
      AND OLD.skill_set_id IS NOT NULL
     OR NEW.root_state_key <> OLD.root_state_key OR NEW.policy_hash <> OLD.policy_hash
     OR NEW.search_session_id <> OLD.search_session_id OR NEW.step_id <> OLD.step_id
     OR NEW.config_artifact_id <> OLD.config_artifact_id
    )
    BEGIN SELECT RAISE(ABORT, 'decision identity and policy are immutable'); END;
    """,
]

_DROP_ORDER = [
    "cb_skill_set_members",
    "cb_skill_sets",
    "cb_skill_versions",
]


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)


def downgrade() -> None:
    """Feature rollback. Refuses to drop when skill data exists (PRD §23.3)."""
    bind = op.get_bind()
    version_rows = bind.execute(sa.text("SELECT COUNT(*) FROM cb_skill_versions")).scalar()
    if version_rows:
        raise RuntimeError(
            "refusing destructive rollback: cb_skill_versions holds "
            f"{version_rows} row(s); archive or clear skill data first"
        )
    for table in _DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    # NOTE: SQLite drops triggers with their tables; the two decision columns
    # are left in place (non-destructive additive rollback).
