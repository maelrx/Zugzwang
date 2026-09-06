"""step-level effective assistance projection (reconstructed 2026-09-05)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04 (original) / 2026-09-05 (reconstruction)

The original 0006 sources were lost (only the compiled .pyc survived);
this file was reconstructed from the .pyc bytecode — upgrade adds column
``steps.effective_assistance`` — and from the live workspace database DDL.
Upgrade is idempotent: the column is added only when missing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    if not _column_exists("steps", "effective_assistance"):
        op.add_column("steps", sa.Column("effective_assistance", sa.String(8), nullable=True))


def downgrade() -> None:
    if _column_exists("steps", "effective_assistance"):
        op.drop_column("steps", "effective_assistance")
