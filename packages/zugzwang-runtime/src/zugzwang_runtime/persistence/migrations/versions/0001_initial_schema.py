"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("experiment_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_manifest_artifact_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("experiment_id", sa.String(32), nullable=True),
        sa.Column("condition_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resolved_manifest_artifact_id", sa.String(128), nullable=True),
        sa.Column("protocol_hash", sa.String(64), nullable=False),
        sa.Column("declared_assistance", sa.String(8), nullable=False),
        sa.Column("effective_assistance", sa.String(8), nullable=True),
        sa.Column("started_at", sa.String(32), nullable=True),
        sa.Column("finished_at", sa.String(32), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("projection_version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "episodes",
        sa.Column("episode_id", sa.String(32), primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(128), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("initial_state_artifact_id", sa.String(128), nullable=True),
        sa.Column("final_state_artifact_id", sa.String(128), nullable=True),
        sa.Column("effective_assistance", sa.String(8), nullable=True),
    )
    op.create_table(
        "steps",
        sa.Column("step_id", sa.String(32), primary_key=True),
        sa.Column("episode_id", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("observation_artifact_id", sa.String(128), nullable=True),
        sa.Column("action_json", sa.JSON(), nullable=True),
        sa.Column("transition_artifact_id", sa.String(128), nullable=True),
        sa.Column("committed_at", sa.String(32), nullable=True),
    )
    op.create_table(
        "attempts",
        sa.Column("attempt_id", sa.String(32), primary_key=True),
        sa.Column("step_id", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_artifact_id", sa.String(128), nullable=True),
        sa.Column("response_artifact_id", sa.String(128), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("outcome_unknown", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=True),
        sa.Column("cost_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(32), primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("episode_id", sa.String(32), nullable=True),
        sa.Column("step_id", sa.String(32), nullable=True),
        sa.Column("attempt_id", sa.String(32), nullable=True),
        sa.Column("stream_type", sa.String(24), nullable=False),
        sa.Column("stream_id", sa.String(32), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("artifact_refs_json", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
    )
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(128), primary_key=True),
        sa.Column("algorithm", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("compression", sa.String(32), nullable=True),
        sa.Column("relative_path", sa.String(256), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("redaction_policy", sa.String(32), nullable=True),
    )
    op.create_table(
        "metric_observations",
        sa.Column("metric_observation_id", sa.String(32), primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("episode_id", sa.String(32), nullable=True),
        sa.Column("step_id", sa.String(32), nullable=True),
        sa.Column("metric_definition_id", sa.String(128), nullable=False),
        sa.Column("metric_version", sa.String(16), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("dimensions_json", sa.JSON(), nullable=False),
        sa.Column("provenance_artifact_id", sa.String(128), nullable=True),
        sa.Column("evaluator_id", sa.String(128), nullable=False),
        sa.Column("evaluator_version", sa.String(16), nullable=False),
    )
    op.create_table(
        "budget_ledger",
        sa.Column("ledger_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("reserved", sa.String(40), nullable=False),
        sa.Column("used", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "checkpoints",
        sa.Column("checkpoint_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("stream_type", sa.String(24), nullable=False),
        sa.Column("stream_id", sa.String(32), nullable=False),
        sa.Column("sequence_committed", sa.Integer(), nullable=False),
        sa.Column("state_artifact_id", sa.String(128), nullable=True),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_events_stream", "events", ["stream_type", "stream_id", "sequence_no"])
    op.create_index("ix_episodes_run", "episodes", ["run_id"])
    op.create_index("ix_steps_episode", "steps", ["episode_id"])
    op.create_index("ix_attempts_step", "attempts", ["step_id"])


def downgrade() -> None:
    for table in (
        "checkpoints",
        "budget_ledger",
        "metric_observations",
        "artifacts",
        "events",
        "attempts",
        "steps",
        "episodes",
        "runs",
        "experiments",
    ):
        op.drop_table(table)
