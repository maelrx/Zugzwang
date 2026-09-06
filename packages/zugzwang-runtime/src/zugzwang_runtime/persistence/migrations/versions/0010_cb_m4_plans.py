"""CognitiveBoard CB-M4: investigations and plans (PRD §43.2, ZGW-0100).

DDL transcribed from the normative §43.2 target schema: decision-anchored
investigations with status lifecycle, episode-scoped conditional plans with
perspective, and the episode guard (a plan belongs to its source decision's
episode). Plans and investigations move forward by new revisions — status
columns transition through the writer, never by direct UPDATE of identity.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE cb_investigations (
        investigation_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        anchor_node_id TEXT NOT NULL,
        root_action TEXT,
        status TEXT NOT NULL CHECK (status IN
            ('open','investigating','provisionally_answered','needs_review','budget_exhausted','abandoned')),
        revision INTEGER NOT NULL CHECK (revision >= 0),
        payload_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        latest_event_id TEXT NOT NULL REFERENCES events(event_id),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(decision_id, anchor_node_id) REFERENCES cb_node_bindings(decision_id, node_id)
    )
    """,
    "CREATE INDEX cb_investigation_open_idx ON cb_investigations(decision_id, status)",
    """
    CREATE TABLE cb_plans (
        plan_id TEXT NOT NULL PRIMARY KEY,
        episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
        source_decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        perspective TEXT NOT NULL CHECK (perspective IN ('white','black')),
        status TEXT NOT NULL CHECK (status IN ('active','needs_review','revised','abandoned','achieved')),
        revision INTEGER NOT NULL CHECK (revision >= 0),
        payload_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        latest_event_id TEXT NOT NULL REFERENCES events(event_id),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER cb_plan_episode_guard BEFORE INSERT ON cb_plans
    WHEN NEW.episode_id <> (
     SELECT steps.episode_id FROM cb_decisions JOIN steps ON cb_decisions.step_id = steps.step_id
     WHERE cb_decisions.decision_id = NEW.source_decision_id)
    BEGIN SELECT RAISE(ABORT, 'plan belongs to another episode'); END;
    """,
]

_DROP_ORDER = [
    "cb_plans",
    "cb_investigations",
]


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)


def downgrade() -> None:
    """Feature rollback. Refuses to drop when plan data exists (PRD §23.3)."""
    bind = op.get_bind()
    plan_rows = bind.execute(sa.text("SELECT COUNT(*) FROM cb_plans")).scalar()
    if plan_rows:
        raise RuntimeError(
            "refusing destructive rollback: cb_plans holds "
            f"{plan_rows} row(s); archive or clear plan data first"
        )
    for table in _DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
