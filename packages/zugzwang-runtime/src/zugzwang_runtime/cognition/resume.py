"""CognitiveBoard resume (PRD §38.9; CB-WO-08 + ZGW-0101).

Resume rebuilds a decision's runtime state from its journal rows + CAS —
never from provider or engine calls (TEST-058). ``resume_decision`` reopens
the journal on the same files and returns a ``ResumePlan`` with the REAL
reconstructed state: the decision record, every bound node with its FEN
(restored from the durable state snapshots), the exposure transcript with
loaded payloads, the round journal, the per-unit budget balance, and any
operation left PREPARED by a crash (reconciled, never silently re-executed:
TEST-038/TEST-040). ``resume_session`` goes one step further and rebuilds a
continuable ``DecisionSession`` — the loop can resume driving the decision
in a NEW process. ``recover_missing_exposures`` repairs the legacy window of
COMMITTED operations without an observation; ``settle_stale_operations``
fails PREPARED orphans explicitly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, cast

import sqlalchemy as sa

from zugzwang_core.domain.canonical import sha256_hex
from zugzwang_core.domain.cognition import observation_id_v3

from ..persistence.cognition import CognitionJournal

_TOOL_KIND_BY_NAME = {
    "board_observe": "view",
    "board_inspect": "inspect",
    "board_expand": "expand",
    "board_compare": "compare",
}


@dataclass(slots=True)
class ResumePlan:
    """What a crashed decision needs to continue safely."""

    decision_id: str
    status: str
    search_session_id: str
    root_node_id: str
    next_round_ordinal: int
    operations_settled: int
    operations_open: list[str]
    exposure_watermark: int
    budget_balance: dict[str, dict[str, int]]
    selected_action: str | None = None
    rounds: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])
    nodes: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])
    states: dict[str, Any] = field(default_factory=dict["str", Any])
    transcript: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])


def resume_decision(
    journal: CognitionJournal,
    decision_id: str,
    *,
    state_loader: Any | None = None,
    payload_loader: Any | None = None,
) -> ResumePlan:
    """Rebuild runtime state for ``decision_id`` from journal + CAS rows.

    ``state_loader(state_key)`` optionally restores the INTEGRAL state behind
    each bound node (chess states are restored from their snapshot artifacts
    — never replayed through an engine); ``payload_loader(artifact_id)``
    loads observation payloads so the transcript is real content, not ids.
    """
    with journal.connect() as conn:
        decision = conn.execute(
            sa.text(
                "SELECT status, selected_action, search_session_id FROM cb_decisions "
                "WHERE decision_id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
        if decision is None:
            from ..persistence.cognition import DecisionJournalError

            raise DecisionJournalError("SEMANTICS_MISMATCH", f"unknown decision {decision_id!r}")
        status, selected_action, search_session_id = decision[0], decision[1], decision[2]
        max_round = conn.execute(
            sa.text("SELECT COALESCE(MAX(ordinal), 0) FROM cb_rounds WHERE decision_id = :id"),
            {"id": decision_id},
        ).fetchone()
        rounds = conn.execute(
            sa.text(
                "SELECT ordinal, purpose, status FROM cb_rounds "
                "WHERE decision_id = :id ORDER BY ordinal"
            ),
            {"id": decision_id},
        ).fetchall()
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
        nodes = conn.execute(
            sa.text(
                "SELECT b.node_id, b.state_key, b.depth_plies, s.position_key "
                "FROM cb_node_bindings b JOIN cb_state_snapshots s USING (state_key) "
                "WHERE b.decision_id = :id ORDER BY b.created_sequence, b.node_id"
            ),
            {"id": decision_id},
        ).fetchall()
        observations = conn.execute(
            sa.text(
                "SELECT exposure_sequence, kind, node_id, operation_id, "
                "payload_artifact_id, semantic_hash, available_before_selection "
                "FROM cb_observations WHERE decision_id = :id ORDER BY exposure_sequence"
            ),
            {"id": decision_id},
        ).fetchall()
    balance = journal.reconcile_budget(decision_id)

    states: dict[str, Any] = {}
    node_rows: list[dict[str, Any]] = []
    for node_id, state_key, depth_plies, position_key in nodes:
        fen: str | None = None
        state: Any = None
        if state_loader is not None:
            state = state_loader(str(state_key))
            fen = getattr(state, "fen", None)
        node_rows.append(
            {
                "node_id": node_id,
                "state_key": state_key,
                "depth_plies": int(depth_plies),
                "position_key": position_key,
                "fen": fen,
            }
        )
        if state is not None:
            states[node_id] = state
    transcript = [
        {
            "exposure_sequence": int(row[0]),
            "kind": row[1],
            "node_id": row[2],
            "operation_id": row[3],
            "payload_artifact_id": row[4],
            "semantic_hash": row[5],
            "available_before_selection": bool(row[6]),
            "payload": payload_loader(str(row[4])) if payload_loader is not None else None,
        }
        for row in observations
    ]
    return ResumePlan(
        decision_id=decision_id,
        status=status,
        search_session_id=search_session_id,
        root_node_id=node_rows[0]["node_id"] if node_rows else "",
        next_round_ordinal=int(max_round[0]) + 1 if max_round else 1,
        operations_settled=int(settled[0]) if settled else 0,
        operations_open=[row[0] for row in open_rows],
        exposure_watermark=int(watermark[0]) if watermark else 0,
        budget_balance={unit: dict(values) for unit, values in balance.items()},
        selected_action=selected_action,
        rounds=[{"ordinal": r[0], "purpose": r[1], "status": r[2]} for r in rounds],
        nodes=node_rows,
        states=states,
        transcript=transcript,
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


def settle_stale_operations(
    journal: CognitionJournal, decision_id: str, *, error_code: str = "PERSISTENCE_FAILED"
) -> int:
    """Explicitly FAIL operations a crash left PREPARED (recovery §14.5).

    A PREPARED operation has no settled effect; failing it keeps the journal
    total (no row is erased) and lets a retry with a FRESH idempotency key
    re-attempt the work. It never marks an operation COMMITTED.
    """
    stale = open_operations(journal, decision_id)
    for row in stale:
        journal.settle_tool_operation(
            operation_id=str(row["operation_id"]),
            decision_id=decision_id,
            status="FAILED",
            result_artifact_id=None,
            error_code=error_code,
        )
    return len(stale)


def recover_missing_exposures(
    journal: CognitionJournal,
    decision_id: str,
    *,
    loader: Any,
) -> int:
    """Re-expose COMMITTED operations whose observation row is missing.

    Repairs a settle/exposure window (legacy rows or a foreign writer): the
    result artifact is durable and content-addressed, so the observation is
    rebuilt from stored rows — node identity from the operation's own
    arguments artifact, semantic hash from the result bytes — WITHOUT
    re-executing any effect (TEST-038 direction).
    """
    with journal.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT o.operation_id, o.round_id, r.ordinal, o.result_artifact_id, "
                "o.arguments_artifact_id, o.tool_name FROM cb_tool_operations o "
                "JOIN cb_decisions d ON d.decision_id = o.decision_id "
                "LEFT JOIN cb_observations e ON e.operation_id = o.operation_id "
                "LEFT JOIN cb_rounds r ON r.round_id = o.round_id "
                "WHERE o.decision_id = :id AND o.status = 'COMMITTED' "
                "AND e.operation_id IS NULL ORDER BY o.created_at"
            ),
            {"id": decision_id},
        ).fetchall()
        policy = conn.execute(
            sa.text("SELECT policy_hash FROM cb_decisions WHERE decision_id = :id"),
            {"id": decision_id},
        ).fetchone()
    if not rows or policy is None:
        return 0
    recovered = 0
    for operation_id, round_id, ordinal, artifact_id, arguments_artifact_id, tool_name in rows:
        node_id = ""
        try:
            arguments_bytes = loader(str(arguments_artifact_id))
            if arguments_bytes is not None:
                parsed: Any = json.loads(arguments_bytes.decode("utf-8"))
                if isinstance(parsed, dict):
                    record = cast("dict[str, Any]", parsed)
                    raw_node = record.get("node_id")
                    node_id = raw_node if isinstance(raw_node, str) else ""
        except (ValueError, AttributeError):
            node_id = ""
        result_bytes = loader(str(artifact_id)) or b""
        semantic_hash = sha256_hex(result_bytes)
        kind = _TOOL_KIND_BY_NAME.get(str(tool_name), "view")
        # One sequence allocation per recovered exposure: the id and the row
        # must carry the SAME number (two MAX+1 calls with no insert between
        # them return the same value, which is consistent but fragile).
        exposure_sequence = journal.next_exposure_sequence(decision_id)
        journal.record_observation(
            observation_id=observation_id_v3(
                decision_id, semantic_hash, int(ordinal or 0), exposure_sequence
            ),
            decision_id=decision_id,
            node_id=node_id,
            round_id=round_id,
            operation_id=str(operation_id),
            kind=kind,
            payload_artifact_id=str(artifact_id),
            semantic_hash=semantic_hash,
            policy_hash=str(policy[0]),
            exposure_sequence=exposure_sequence,
            available_before_selection=True,
        )
        recovered += 1
    return recovered


def resume_session(
    *,
    plan: ResumePlan,
    journal: CognitionJournal,
    perception: Any,
    cas: Any,
    engine: Any,
    clock: Any | None = None,
) -> Any:
    """Rebuild a CONTINUABLE DecisionSession from a ResumePlan (§14.4).

    The expansion graph is re-anchored from the durable states, the budget
    authority is rebuilt from the journal's own reconciliation (not memory),
    and the loop can drive further rounds in this new process.
    """
    from zugzwang_chess.environment.standard import StandardChessRulesKernel

    from ..search.workspace import SearchWorkspace
    from .session import DecisionSession, cas_artifact_loader, cas_artifact_sink

    if plan.root_node_id not in plan.states:
        raise ValueError(
            "resume_session requires state_loader states; call resume_decision "
            "with state_loader before rebuilding the session"
        )
    kernel = StandardChessRulesKernel()
    workspace = SearchWorkspace(
        kernel=kernel,
        root_state=plan.states[plan.root_node_id],
        session_id=plan.search_session_id,
    )
    for node in plan.nodes:
        if node["node_id"] == plan.root_node_id:
            continue
        state = plan.states.get(str(node["node_id"]))
        if state is not None:
            workspace.register_anchor(
                node_id=str(node["node_id"]), state=state, depth=int(node["depth_plies"])
            )
    tool_remaining = int(plan.budget_balance.get("tool_operations", {}).get("remaining", 0))
    model_remaining = int(plan.budget_balance.get("model_calls", {}).get("remaining", 0))
    sink = cas_artifact_sink(cas, engine, clock or (lambda: "1970-01-01T00:00:00Z"))
    loader = cas_artifact_loader(cas)
    from .broker import CognitionToolBroker, DecisionBudget
    from .session import ROOT_ROUND_ID_SUFFIX, SessionComponents

    with journal.connect() as conn:
        row = conn.execute(
            sa.text("SELECT policy_hash, step_id FROM cb_decisions WHERE decision_id = :id"),
            {"id": plan.decision_id},
        ).fetchone()
    policy_hash = str(row[0]) if row is not None else "0" * 64

    components = SessionComponents(
        journal=journal,
        perception=perception,
        cas=cas,
        engine=engine,
        sink=sink,
        loader=loader,
        rules_kernel=kernel,
        workspace=workspace,
        policy_hash=policy_hash,
        max_batch=16,
        max_argument_bytes=8192,
        search_session_id=plan.search_session_id,
        clock=clock or (lambda: "1970-01-01T00:00:00Z"),
    )
    broker = CognitionToolBroker(
        decision_id=plan.decision_id,
        round_id=f"{plan.decision_id}:{ROOT_ROUND_ID_SUFFIX}",
        round_ordinal=1,
        journal=journal,
        perception=perception,
        policy_hash=policy_hash,
        states=dict(plan.states),
        budget=DecisionBudget(tool_operations=tool_remaining, model_calls=model_remaining),
        artifact_sink=sink,
        artifact_loader=loader,
        rules_kernel=kernel,
        search_workspace=workspace,
        search_session_id=plan.search_session_id,
    )
    session = DecisionSession(decision_id=plan.decision_id, broker=broker, journal=journal)
    session.attach_components(components)
    return session
