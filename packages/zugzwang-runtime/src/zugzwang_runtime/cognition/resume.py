"""CognitiveBoard resume (PRD §38.9; CB-WO-08).

Resume rebuilds a decision's runtime state from its journal rows + CAS —
never from provider or engine calls (TEST-058). ``resume_decision`` reopens
the journal on the same files, replays rounds / operations / observations /
budget entries, and returns a ``ResumePlan``: the next round ordinal, the
reconstructed tool-operation balance, the exposure watermark, and any
operation left PREPARED (a crash between record and settle) that must be
reconciled — never silently re-executed (TEST-038) and never applied twice
(TEST-040).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa

from ..persistence.cognition import CognitionJournal


@dataclass(slots=True)
class ResumePlan:
    """What a crashed decision needs to continue safely."""

    decision_id: str
    status: str
    next_round_ordinal: int
    operations_settled: int
    operations_open: list[str]
    exposure_watermark: int
    budget_balance: dict[str, dict[str, int]]
    selected_action: str | None = None


def resume_decision(journal: CognitionJournal, decision_id: str) -> ResumePlan:
    """Rebuild runtime state for ``decision_id`` from journal + CAS rows."""
    with journal.connect() as conn:
        decision = conn.execute(
            sa.text("SELECT status, selected_action FROM cb_decisions WHERE decision_id = :id"),
            {"id": decision_id},
        ).fetchone()
        if decision is None:
            from ..persistence.cognition import DecisionJournalError

            raise DecisionJournalError("SEMANTICS_MISMATCH", f"unknown decision {decision_id!r}")
        status, selected_action = decision[0], decision[1]
        max_round = conn.execute(
            sa.text("SELECT COALESCE(MAX(ordinal), 0) FROM cb_rounds WHERE decision_id = :id"),
            {"id": decision_id},
        ).fetchone()
        settled = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM cb_tool_operations WHERE decision_id = :id "
                "AND status IN ('COMMITTED', 'REJECTED', 'FAILED')"
            ),
            {"id": decision_id},
        ).fetchone()
        open_rows = conn.execute(
            sa.text(
                "SELECT operation_id FROM cb_tool_operations WHERE decision_id = :id "
                "AND status = 'PREPARED' ORDER BY created_at"
            ),
            {"id": decision_id},
        ).fetchall()
        watermark = conn.execute(
            sa.text(
                "SELECT COALESCE(MAX(exposure_sequence), 0) FROM cb_observations "
                "WHERE decision_id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
        conn.commit()
    balance = journal.reconcile_budget(decision_id)
    return ResumePlan(
        decision_id=decision_id,
        status=status,
        next_round_ordinal=int(max_round[0]) + 1 if max_round else 1,
        operations_settled=int(settled[0]) if settled else 0,
        operations_open=[row[0] for row in open_rows],
        exposure_watermark=int(watermark[0]) if watermark else 0,
        budget_balance={unit: dict(values) for unit, values in balance.items()},
        selected_action=selected_action,
    )


def open_operations(journal: CognitionJournal, decision_id: str) -> list[dict[str, Any]]:
    """Operations left PREPARED by a crash: reconcile, never re-execute blindly."""
    with journal.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT operation_id, round_id, tool_name, idempotency_key, status "
                "FROM cb_tool_operations WHERE decision_id = :id AND status = 'PREPARED' "
                "ORDER BY created_at"
            ),
            {"id": decision_id},
        ).fetchall()
        conn.commit()
    return [
        {
            "operation_id": row[0],
            "round_id": row[1],
            "tool_name": row[2],
            "idempotency_key": row[3],
            "status": row[4],
        }
        for row in rows
    ]
