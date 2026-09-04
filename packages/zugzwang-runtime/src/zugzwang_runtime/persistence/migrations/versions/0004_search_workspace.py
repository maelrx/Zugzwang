"""model-only search workspace projections

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("steps", sa.Column("search_session_id", sa.String(32), nullable=True))
    op.add_column("steps", sa.Column("search_graph_artifact_id", sa.String(128), nullable=True))
    op.create_table(
        "search_sessions",
        sa.Column("search_session_id", sa.String(32), primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("episode_id", sa.String(32), nullable=True),
        sa.Column("step_id", sa.String(32), nullable=True),
        sa.Column("algorithm", sa.String(128), nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("root_node_id", sa.String(128), nullable=False),
        sa.Column("budgets_json", sa.JSON(), nullable=False),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("finished_at", sa.String(32), nullable=True),
    )
    op.create_table(
        "search_nodes",
        sa.Column("node_id", sa.String(128), primary_key=True),
        sa.Column("search_session_id", sa.String(32), nullable=False),
        sa.Column("parent_id", sa.String(128), nullable=True),
        sa.Column("position_key", sa.String(128), nullable=False),
        sa.Column("trajectory_key", sa.String(128), nullable=False),
        sa.Column("state_ref", sa.String(256), nullable=False),
        sa.Column("action_from_parent", sa.String(32), nullable=True),
        sa.Column("root_action", sa.String(32), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("side_to_move", sa.String(8), nullable=True),
        sa.Column("terminal", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("analysis_ref", sa.String(256), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
    )
    op.create_table(
        "search_edges",
        sa.Column("edge_id", sa.String(128), primary_key=True),
        sa.Column("search_session_id", sa.String(32), nullable=False),
        sa.Column("parent_node_id", sa.String(128), nullable=False),
        sa.Column("child_node_id", sa.String(128), nullable=True),
        sa.Column("proposed_action", sa.String(32), nullable=False),
        sa.Column("legal", sa.Integer(), nullable=False),
        sa.Column("rejection_reason", sa.String(128), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_table(
        "search_retrieval_events",
        sa.Column("retrieval_event_id", sa.String(32), primary_key=True),
        sa.Column("search_session_id", sa.String(32), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("retriever", sa.String(128), nullable=False),
        sa.Column("budget_json", sa.JSON(), nullable=False),
        sa.Column("result_refs_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_search_sessions_run", "search_sessions", ["run_id"])
    op.create_index("ix_search_nodes_session", "search_nodes", ["search_session_id"])
    op.create_index("ix_search_nodes_position", "search_nodes", ["position_key"])
    op.create_index("ix_search_edges_session", "search_edges", ["search_session_id"])


def downgrade() -> None:
    op.drop_column("steps", "search_graph_artifact_id")
    op.drop_column("steps", "search_session_id")
    op.drop_index("ix_search_edges_session", table_name="search_edges")
    op.drop_index("ix_search_nodes_position", table_name="search_nodes")
    op.drop_index("ix_search_nodes_session", table_name="search_nodes")
    op.drop_index("ix_search_sessions_run", table_name="search_sessions")
    op.drop_table("search_retrieval_events")
    op.drop_table("search_edges")
    op.drop_table("search_nodes")
    op.drop_table("search_sessions")
