"""effective assistance audit projections

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("assistance_violated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "episodes",
        sa.Column("assistance_violated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "steps",
        sa.Column("assistance_violated", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("steps", "assistance_violated")
    op.drop_column("episodes", "assistance_violated")
    op.drop_column("runs", "assistance_violated")
