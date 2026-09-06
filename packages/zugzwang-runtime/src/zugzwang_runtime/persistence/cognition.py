"""CognitiveBoard decision journal writer (PRD §23, §12.2, §21; CB-WO-04).

Repository layer over the CB-M1 tables. Every write goes through this
repository (PRD §23.2: "todos os writes passam pelo writer/repository").
Immutable rows are never updated; decision status transitions are validated
against the §12.2 aggregate table before the write; the budget journal is
append-only and reconcilable against the run's budget_ledger.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from .database import Database

_DECISION_TRANSITIONS: dict[str, frozenset[str]] = {
    "PREPARING": frozenset({"READY"}),
    "READY": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"READY", "OUTCOME_UNKNOWN", "SELECTED", "FAILED"}),
    "OUTCOME_UNKNOWN": frozenset({"READY", "PAUSED"}),
    "PAUSED": frozenset(),
    "SELECTED": frozenset({"COMMITTED"}),
    "COMMITTED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}

_ROUND_OPEN_STATUSES = frozenset({"REQUEST_PENDING", "RESPONSE_COMMITTED", "OUTCOME_UNKNOWN"})
_ROUND_COMPLETION_TARGETS = frozenset(
    {"RESPONSE_COMMITTED", "TOOLS_COMMITTED", "OUTCOME_UNKNOWN", "FAILED"}
)


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class CognitionJournal:
    """Writer for the CB-M1 decision journal tables (single logical writer).

    ``clock`` is injectable for deterministic tests (CODING_STANDARDS:
    injected clocks); production uses UTC wall time.
    """

    def __init__(self, database: Database, clock: Callable[[], str] | None = None) -> None:
        self._database = database
        self._clock = clock or _now

    def _connect(self) -> Connection:
        return self._database.engine().connect()

    # -- state snapshots ------------------------------------------------------

    def ensure_state_snapshot(
        self,
        *,
        state_key: str,
        state_schema_version: str,
        rules_version: str,
        variant: str,
        position_key: str,
        history_completeness: str,
        state_artifact_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT OR IGNORE INTO cb_state_snapshots "
                    "(state_key, state_schema_version, rules_version, variant, position_key, "
                    "history_completeness, state_artifact_id, created_at) "
                    "VALUES (:state_key, :state_schema_version, :rules_version, :variant, "
                    ":position_key, :history_completeness, :state_artifact_id, :created_at)"
                ),
                {
                    "state_key": state_key,
                    "state_schema_version": state_schema_version,
                    "rules_version": rules_version,
                    "variant": variant,
                    "position_key": position_key,
                    "history_completeness": history_completeness,
                    "state_artifact_id": state_artifact_id,
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    # -- decisions ------------------------------------------------------------

    def create_decision(
        self,
        *,
        decision_id: str,
        step_id: str,
        decision_ordinal: int,
        search_session_id: str,
        root_state_key: str,
        strategy_id: str,
        strategy_version: str,
        interaction_mode: str,
        policy_hash: str,
        config_artifact_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_decisions (decision_id, step_id, decision_ordinal, "
                    "search_session_id, root_state_key, status, strategy_id, strategy_version, "
                    "interaction_mode, policy_hash, config_artifact_id, created_at) "
                    "VALUES (:decision_id, :step_id, :decision_ordinal, :search_session_id, "
                    ":root_state_key, 'PREPARING', :strategy_id, :strategy_version, "
                    ":interaction_mode, :policy_hash, :config_artifact_id, :created_at)"
                ),
                {
                    "decision_id": decision_id,
                    "step_id": step_id,
                    "decision_ordinal": decision_ordinal,
                    "search_session_id": search_session_id,
                    "root_state_key": root_state_key,
                    "strategy_id": strategy_id,
                    "strategy_version": strategy_version,
                    "interaction_mode": interaction_mode,
                    "policy_hash": policy_hash,
                    "config_artifact_id": config_artifact_id,
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    def transition_decision(
        self,
        decision_id: str,
        new_status: str,
        *,
        selected_action: str | None = None,
        selection_source: str | None = None,
    ) -> None:
        """Transition the aggregate status; only §12.2 edges are legal.

        Entering SELECTED/COMMITTED requires the selected action and its
        source (model or runtime_fallback) — the DDL check is enforced here
        with a machine-coded rejection before the write.
        """
        with self._connect() as conn:
            row = conn.execute(
                sa.text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
                {"id": decision_id},
            ).fetchone()
            if row is None:
                raise DecisionJournalError(
                    "SEMANTICS_MISMATCH", f"unknown decision {decision_id!r}"
                )
            current = row[0]
            if new_status not in _DECISION_TRANSITIONS.get(current, frozenset()):
                raise DecisionJournalError(
                    "STATE_REPLAY_MISMATCH",
                    f"illegal decision transition {current} -> {new_status}",
                )
            if new_status in {"SELECTED", "COMMITTED"} and (
                not selected_action or not selection_source
            ):
                raise DecisionJournalError(
                    "INVALID_ARGUMENTS",
                    f"transition to {new_status} requires selected_action and selection_source",
                )
            finished = ", finished_at = :finished_at" if new_status in _TERMINAL_STATUSES else ""
            selection = (
                ", selected_action = :selected_action, selection_source = :selection_source"
                if selected_action is not None
                else ""
            )
            params: dict[str, Any] = {
                "id": decision_id,
                "new_status": new_status,
                "selected_action": selected_action,
                "selection_source": selection_source,
            }
            if finished:
                params["finished_at"] = self._clock()
            conn.execute(
                sa.text(
                    f"UPDATE cb_decisions SET status = :new_status{finished}{selection} "
                    "WHERE decision_id = :id"
                ),
                params,
            )
            conn.commit()

    def decision_status(self, decision_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                sa.text("SELECT status FROM cb_decisions WHERE decision_id = :id"),
                {"id": decision_id},
            ).fetchone()
        return row[0] if row else None

    # -- node bindings ---------------------------------------------------------

    def bind_node(
        self,
        *,
        decision_id: str,
        node_id: str,
        state_key: str,
        depth_plies: int,
        created_sequence: int,
    ) -> None:
        """Bind an existing search node to the decision scope (§23.2)."""
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_node_bindings (decision_id, node_id, state_key, "
                    "depth_plies, created_sequence) "
                    "VALUES (:decision_id, :node_id, :state_key, :depth_plies, :created_sequence)"
                ),
                {
                    "decision_id": decision_id,
                    "node_id": node_id,
                    "state_key": state_key,
                    "depth_plies": depth_plies,
                    "created_sequence": created_sequence,
                },
            )
            conn.commit()

    # -- rounds ---------------------------------------------------------------

    def add_round(
        self,
        *,
        round_id: str,
        decision_id: str,
        ordinal: int,
        purpose: str,
        context_artifact_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_rounds (round_id, decision_id, ordinal, purpose, status, "
                    "context_artifact_id, created_at) "
                    "VALUES (:round_id, :decision_id, :ordinal, :purpose, 'PREPARED', "
                    ":context_artifact_id, :created_at)"
                ),
                {
                    "round_id": round_id,
                    "decision_id": decision_id,
                    "ordinal": ordinal,
                    "purpose": purpose,
                    "context_artifact_id": context_artifact_id,
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    def complete_round(self, round_id: str, decision_id: str, status: str) -> None:
        """Close a round from an open boundary status (§12.2 round statuses)."""
        if status not in _ROUND_COMPLETION_TARGETS:
            raise DecisionJournalError(
                "INVALID_ARGUMENTS", f"round cannot complete into {status!r}"
            )
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT status FROM cb_rounds "
                    "WHERE round_id = :round_id AND decision_id = :decision_id"
                ),
                {"round_id": round_id, "decision_id": decision_id},
            ).fetchone()
            if row is None or row[0] not in _ROUND_OPEN_STATUSES:
                raise DecisionJournalError(
                    "STATE_REPLAY_MISMATCH",
                    f"round {round_id!r} not open for completion",
                )
            conn.execute(
                sa.text(
                    "UPDATE cb_rounds SET status = :status, completed_at = :completed_at "
                    "WHERE round_id = :round_id AND decision_id = :decision_id "
                    "AND completed_at IS NULL"
                ),
                {
                    "status": status,
                    "completed_at": self._clock(),
                    "round_id": round_id,
                    "decision_id": decision_id,
                },
            )
            conn.commit()

    # -- tool operations (idempotent) -----------------------------------------

    def record_tool_operation(
        self,
        *,
        operation_id: str,
        decision_id: str,
        round_id: str,
        provider_tool_call_id: str,
        idempotency_key: str,
        tool_name: str,
        arguments_hash: str,
        arguments_artifact_id: str,
    ) -> tuple[str, bool]:
        """Insert a PREPARED operation; replay of the same idempotency key
        returns the existing operation id without creating a second row
        (durable idempotency, PRD §15/TEST-034)."""
        with self._connect() as conn:
            existing = conn.execute(
                sa.text(
                    "SELECT operation_id, tool_name, arguments_hash FROM cb_tool_operations "
                    "WHERE decision_id = :decision_id AND idempotency_key = :key"
                ),
                {"decision_id": decision_id, "key": idempotency_key},
            ).fetchone()
            # The (round_id, command_ordinal) pair is a durable sequence: the next
            # ordinal is the successor of the current maximum, so every broker
            # sharing this round — including concurrent ones — allocates a fresh
            # slot without colliding (PRD §42.6 ordering).
            row = conn.execute(
                sa.text(
                    "SELECT COALESCE(MAX(command_ordinal), -1) FROM cb_tool_operations "
                    "WHERE round_id = :round_id AND decision_id = :decision_id"
                ),
                {"round_id": round_id, "decision_id": decision_id},
            ).fetchone()
            next_ordinal = int(row[0]) + 1 if row is not None else 0
            if existing is not None:
                # Replay must repeat the same semantic call; a divergent retry
                # is a contract violation, not a new operation (PRD §15).
                if existing[1] != tool_name or existing[2] != arguments_hash:
                    raise DecisionJournalError(
                        "STATE_REPLAY_MISMATCH",
                        "idempotency key replayed with divergent tool or arguments",
                    )
                conn.commit()
                return existing[0], False
            conn.execute(
                sa.text(
                    "INSERT INTO cb_tool_operations (operation_id, decision_id, round_id, "
                    "provider_tool_call_id, command_ordinal, idempotency_key, tool_name, "
                    "arguments_hash, arguments_artifact_id, status, created_at) "
                    "VALUES (:operation_id, :decision_id, :round_id, :provider_tool_call_id, "
                    ":command_ordinal, :idempotency_key, :tool_name, :arguments_hash, "
                    ":arguments_artifact_id, 'PREPARED', :created_at)"
                ),
                {
                    "operation_id": operation_id,
                    "decision_id": decision_id,
                    "round_id": round_id,
                    "provider_tool_call_id": provider_tool_call_id,
                    "command_ordinal": next_ordinal,
                    "idempotency_key": idempotency_key,
                    "tool_name": tool_name,
                    "arguments_hash": arguments_hash,
                    "arguments_artifact_id": arguments_artifact_id,
                    "created_at": self._clock(),
                },
            )
            conn.commit()
            return operation_id, True

    def next_exposure_sequence(self, decision_id: str) -> int:
        """Successor of the current maximum exposure sequence (durable timeline).

        Every broker sharing a decision allocates from this sequence, so
        concurrent brokers never collide on UNIQUE(decision_id,
        exposure_sequence) (PRD §42.6 ordering).
        """
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT COALESCE(MAX(exposure_sequence), 0) FROM cb_observations "
                    "WHERE decision_id = :decision_id"
                ),
                {"decision_id": decision_id},
            ).fetchone()
            conn.commit()
        return int(row[0]) + 1 if row is not None else 1

    def record_observation(
        self,
        *,
        observation_id: str,
        decision_id: str,
        node_id: str,
        round_id: str | None,
        operation_id: str | None,
        kind: str,
        payload_artifact_id: str,
        semantic_hash: str,
        policy_hash: str,
        exposure_sequence: int,
        available_before_selection: bool,
    ) -> None:
        """Append one exposure to the decision timeline (§42.6 meta, §23.2)."""
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_observations (observation_id, decision_id, node_id, "
                    "round_id, operation_id, kind, payload_artifact_id, semantic_hash, "
                    "policy_hash, exposure_sequence, available_before_selection, created_at) "
                    "VALUES (:observation_id, :decision_id, :node_id, :round_id, "
                    ":operation_id, :kind, :payload_artifact_id, :semantic_hash, "
                    ":policy_hash, :exposure_sequence, :available_before_selection, :created_at)"
                ),
                {
                    "observation_id": observation_id,
                    "decision_id": decision_id,
                    "node_id": node_id,
                    "round_id": round_id,
                    "operation_id": operation_id,
                    "kind": kind,
                    "payload_artifact_id": payload_artifact_id,
                    "semantic_hash": semantic_hash,
                    "policy_hash": policy_hash,
                    "exposure_sequence": exposure_sequence,
                    "available_before_selection": int(available_before_selection),
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    def settle_tool_operation(
        self,
        *,
        operation_id: str,
        decision_id: str,
        status: str,
        result_artifact_id: str | None,
        error_code: str | None,
        elapsed_us: int | None = None,
    ) -> None:
        """PREPARED -> COMMITTED/REJECTED/FAILED (result artifact mandatory for
        COMMITTED/REJECTED, enforced by the DDL check)."""
        if status not in {"COMMITTED", "REJECTED", "FAILED"}:
            raise DecisionJournalError("INVALID_ARGUMENTS", f"cannot settle into {status!r}")
        if status in {"COMMITTED", "REJECTED"} and result_artifact_id is None:
            raise DecisionJournalError("INVALID_ARGUMENTS", f"{status} requires a result artifact")
        with self._connect() as conn:
            result = conn.execute(
                sa.text(
                    "UPDATE cb_tool_operations SET status = :status, result_artifact_id = "
                    ":result_artifact_id, error_code = :error_code, elapsed_us = :elapsed_us, "
                    "completed_at = :completed_at "
                    "WHERE operation_id = :operation_id AND decision_id = :decision_id "
                    "AND status = 'PREPARED'"
                ),
                {
                    "status": status,
                    "result_artifact_id": result_artifact_id,
                    "error_code": error_code,
                    "elapsed_us": elapsed_us,
                    "completed_at": self._clock(),
                    "operation_id": operation_id,
                    "decision_id": decision_id,
                },
            )
            if result.rowcount != 1:
                raise DecisionJournalError(
                    "STATE_REPLAY_MISMATCH",
                    f"operation {operation_id!r} is not open for settlement",
                )
            conn.commit()

    def result_artifact_id(self, operation_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT result_artifact_id FROM cb_tool_operations "
                    "WHERE operation_id = :operation_id"
                ),
                {"operation_id": operation_id},
            ).fetchone()
        return row[0] if row else None

    def bound_node_ids(self, decision_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                sa.text("SELECT node_id FROM cb_node_bindings WHERE decision_id = :decision_id"),
                {"decision_id": decision_id},
            ).fetchall()
        return [r[0] for r in rows]

    # -- budget journal (append-only, reconcilable) ---------------------------

    def reserve_budget(
        self,
        *,
        reservation_id: str,
        decision_id: str,
        owner_kind: str,
        owner_id: str,
        unit: str,
        amount: int,
        evidence_artifact_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_budget_reservations (reservation_id, decision_id, owner_kind, "
                    "owner_id, unit, amount, status, created_at) "
                    "VALUES (:reservation_id, :decision_id, :owner_kind, :owner_id, :unit, "
                    ":amount, 'RESERVED', :created_at)"
                ),
                {
                    "reservation_id": reservation_id,
                    "decision_id": decision_id,
                    "owner_kind": owner_kind,
                    "owner_id": owner_id,
                    "unit": unit,
                    "amount": amount,
                    "created_at": self._clock(),
                },
            )
            self._append_entry(
                conn,
                decision_id=decision_id,
                reservation_id=reservation_id,
                event_kind="reserve",
                unit=unit,
                delta_reserved=amount,
                delta_used=0,
                evidence_artifact_id=evidence_artifact_id,
            )
            conn.commit()

    def settle_budget(
        self,
        *,
        decision_id: str,
        reservation_id: str,
        unit: str,
        used: int,
        evidence_artifact_id: str,
    ) -> None:
        """Settle at most the reserved amount; overuse requires an explicit
        adjustment entry with evidence (§21)."""
        with self._connect() as conn:
            reserved = self._reserved_amount(conn, decision_id, reservation_id, unit)
            row = conn.execute(
                sa.text(
                    "SELECT COALESCE(SUM(delta_reserved), 0) FROM cb_budget_entries "
                    "WHERE reservation_id = :reservation_id "
                    "AND event_kind = 'adjustment'"
                ),
                {"reservation_id": reservation_id},
            ).fetchone()
            if row is None or row[0] is None:
                raise DecisionJournalError(
                    "SEMANTICS_MISMATCH", "reservation journal missing reserve entry"
                )
            reserved += int(row[0])
            if used > reserved:
                raise DecisionJournalError(
                    "BUDGET_INSUFFICIENT",
                    f"settlement {used} exceeds reservation {reserved} for unit {unit!r}",
                )
            result = conn.execute(
                sa.text(
                    "UPDATE cb_budget_reservations SET status = 'SETTLED', settled_at = :settled_at "
                    "WHERE reservation_id = :reservation_id AND status = 'RESERVED'"
                ),
                {"reservation_id": reservation_id, "settled_at": self._clock()},
            )
            if result.rowcount != 1:
                raise DecisionJournalError(
                    "SEMANTICS_MISMATCH", "reservation is not open for settlement"
                )
            self._append_entry(
                conn,
                decision_id=decision_id,
                reservation_id=reservation_id,
                event_kind="settle",
                unit=unit,
                delta_reserved=0,
                delta_used=used,
                evidence_artifact_id=evidence_artifact_id,
            )
            conn.commit()

    def adjust_budget(
        self,
        *,
        decision_id: str,
        reservation_id: str,
        unit: str,
        delta_reserved: int,
        delta_used: int,
        evidence_artifact_id: str,
    ) -> None:
        """Append an adjustment entry (usage above estimate); the journal keeps
        every prior entry (§21: 'ajuste não apaga o evento anterior')."""
        with self._connect() as conn:
            self._reserved_amount(conn, decision_id, reservation_id, unit)
            self._append_entry(
                conn,
                decision_id=decision_id,
                reservation_id=reservation_id,
                event_kind="adjustment",
                unit=unit,
                delta_reserved=delta_reserved,
                delta_used=delta_used,
                evidence_artifact_id=evidence_artifact_id,
            )
            conn.commit()

    def release_budget(
        self,
        *,
        decision_id: str,
        reservation_id: str,
        unit: str,
        evidence_artifact_id: str,
    ) -> None:
        """Release an unused reservation (RESERVED -> RELEASED, journal entry)."""
        with self._connect() as conn:
            self._reserved_amount(conn, decision_id, reservation_id, unit)
            result = conn.execute(
                sa.text(
                    "UPDATE cb_budget_reservations SET status = 'RELEASED', settled_at = :settled_at "
                    "WHERE reservation_id = :reservation_id AND status = 'RESERVED'"
                ),
                {"reservation_id": reservation_id, "settled_at": self._clock()},
            )
            if result.rowcount != 1:
                raise DecisionJournalError(
                    "SEMANTICS_MISMATCH", "reservation is not open for release"
                )
            self._append_entry(
                conn,
                decision_id=decision_id,
                reservation_id=reservation_id,
                event_kind="release",
                unit=unit,
                delta_reserved=0,
                delta_used=0,
                evidence_artifact_id=evidence_artifact_id,
            )
            conn.commit()

    def reconcile_budget(self, decision_id: str) -> dict[str, dict[str, int]]:
        """Per-unit reconciliation: reserved, used and remaining (never negative)."""
        with self._connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT unit, "
                    "COALESCE(SUM(CASE WHEN event_kind = 'reserve' THEN delta_reserved END), 0) "
                    " + COALESCE(SUM(CASE WHEN event_kind = 'adjustment' THEN delta_reserved END), 0) "
                    "AS reserved_total, "
                    "COALESCE(SUM(delta_used), 0) AS used_total "
                    "FROM cb_budget_entries WHERE decision_id = :decision_id GROUP BY unit"
                ),
                {"decision_id": decision_id},
            ).fetchall()
        report: dict[str, dict[str, int]] = {}
        for unit, reserved_total, used_total in rows:
            remaining = reserved_total - used_total
            if remaining < 0:
                raise DecisionJournalError(
                    "BUDGET_INSUFFICIENT",
                    f"unit {unit!r} reconciles to negative remaining {remaining}",
                )
            report[unit] = {
                "reserved": reserved_total,
                "used": used_total,
                "remaining": remaining,
            }
        return report

    # -- internals ------------------------------------------------------------

    def _reserved_amount(
        self, conn: Connection, decision_id: str, reservation_id: str, unit: str
    ) -> int:
        row = conn.execute(
            sa.text(
                "SELECT amount, unit FROM cb_budget_reservations "
                "WHERE reservation_id = :reservation_id AND decision_id = :decision_id"
            ),
            {"reservation_id": reservation_id, "decision_id": decision_id},
        ).fetchone()
        if row is None:
            raise DecisionJournalError(
                "SEMANTICS_MISMATCH", f"unknown reservation {reservation_id!r}"
            )
        if row[1] != unit:
            raise DecisionJournalError(
                "SEMANTICS_MISMATCH", f"reservation unit {row[1]!r} != {unit!r}"
            )
        return int(row[0])

    def _append_entry(
        self,
        conn: Connection,
        *,
        decision_id: str,
        reservation_id: str,
        event_kind: str,
        unit: str,
        delta_reserved: int,
        delta_used: int,
        evidence_artifact_id: str,
    ) -> None:
        row = conn.execute(
            sa.text(
                "SELECT COALESCE(MAX(sequence_no), -1) FROM cb_budget_entries "
                "WHERE decision_id = :decision_id"
            ),
            {"decision_id": decision_id},
        ).fetchone()
        if row is None or row[0] is None:
            raise DecisionJournalError("SEMANTICS_MISMATCH", "journal sequence missing")
        sequence_no = int(row[0]) + 1
        conn.execute(
            sa.text(
                "INSERT INTO cb_budget_entries (entry_id, decision_id, reservation_id, "
                "sequence_no, event_kind, unit, delta_reserved, delta_used, "
                "evidence_artifact_id, created_at) "
                "VALUES ('be:' || :decision_id || ':' || :sequence_no, :decision_id, "
                ":reservation_id, :sequence_no, :event_kind, :unit, :delta_reserved, "
                ":delta_used, :evidence_artifact_id, :created_at)"
            ),
            {
                "decision_id": decision_id,
                "reservation_id": reservation_id,
                "sequence_no": sequence_no,
                "event_kind": event_kind,
                "unit": unit,
                "delta_reserved": delta_reserved,
                "delta_used": delta_used,
                "evidence_artifact_id": evidence_artifact_id,
                "created_at": self._clock(),
            },
        )


_TERMINAL_STATUSES = frozenset({"COMMITTED", "FAILED", "CANCELLED", "PAUSED"})


class DecisionJournalError(Exception):
    """Journal rejection with machine code (CODING_STANDARDS / Errors)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
