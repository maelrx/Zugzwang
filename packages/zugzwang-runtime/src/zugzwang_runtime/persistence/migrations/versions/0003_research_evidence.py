"""direct evidence references and immutable evaluation generations

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("steps", sa.Column("decision_trace_artifact_id", sa.String(128), nullable=True))
    op.add_column("attempts", sa.Column("wire_request_artifact_id", sa.String(128), nullable=True))
    op.add_column("attempts", sa.Column("wire_response_artifact_id", sa.String(128), nullable=True))
    op.add_column(
        "attempts",
        sa.Column("reasoning_telemetry_artifact_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "metric_observations", sa.Column("evaluation_run_id", sa.String(32), nullable=True)
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_run_id", sa.String(32), primary_key=True),
        sa.Column("source_run_id", sa.String(32), nullable=False),
        sa.Column("evaluator_id", sa.String(128), nullable=False),
        sa.Column("evaluator_version", sa.String(32), nullable=False),
        sa.Column("engine_json", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("finished_at", sa.String(32), nullable=True),
        sa.Column("failure_code", sa.String(128), nullable=True),
    )
    op.create_index("ix_evaluation_runs_source", "evaluation_runs", ["source_run_id"])
    op.create_index(
        "ix_metric_observations_evaluation_run",
        "metric_observations",
        ["evaluation_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_metric_observations_evaluation_run", table_name="metric_observations")
    op.drop_index("ix_evaluation_runs_source", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_column("metric_observations", "evaluation_run_id")
    op.drop_column("attempts", "reasoning_telemetry_artifact_id")
    op.drop_column("attempts", "wire_response_artifact_id")
    op.drop_column("attempts", "wire_request_artifact_id")
    op.drop_column("steps", "decision_trace_artifact_id")
