"""episodes config_json

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("config_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "config_json")
