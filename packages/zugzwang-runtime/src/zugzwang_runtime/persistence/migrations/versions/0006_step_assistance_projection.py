"""step-level effective assistance projection

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("steps", sa.Column("effective_assistance", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("steps", "effective_assistance")
