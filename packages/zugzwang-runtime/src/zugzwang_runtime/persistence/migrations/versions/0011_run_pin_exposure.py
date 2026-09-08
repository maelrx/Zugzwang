"""ZGW-0103 P0: per-run code pin and exposure manifest linkage.

Every run becomes attributable to the exact code that executed it (git SHA +
dirty flag) and to an exposure manifest artifact (declared vs effective
observation policy). ADD COLUMN only — existing evidence rows stay intact.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_DDL = [
    "ALTER TABLE runs ADD COLUMN code_git_sha TEXT",
    "ALTER TABLE runs ADD COLUMN code_dirty INTEGER",
    "ALTER TABLE runs ADD COLUMN exposure_manifest_artifact_id TEXT",
]


def upgrade() -> None:
    for statement in _DDL:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # Attribution columns only: dropping them removes no raw evidence row.
    op.drop_column("runs", "exposure_manifest_artifact_id")
    op.drop_column("runs", "code_dirty")
    op.drop_column("runs", "code_git_sha")
