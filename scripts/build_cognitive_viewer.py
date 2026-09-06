"""Build a redacted, read-only cognitive snapshot for the causal viewer (ZGW-0097).

The browser never opens SQLite or the CAS. This script is the only bridge: it
reuses the CB-WO-08 audit/resume readers over a workspace database and emits
one ``cognitive.json`` snapshot: decision status, rounds, tool operations with
envelope references (operation_id + artifact hashes — TEST-061 timeline is
effective because every row cites the journal bytes), observations, budget
reconciliation and eligible memories. No request/response bodies are copied,
no engine is loaded, and secret-looking keys are redacted (TEST-059/060).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.audit import audit_decision, export_report
from zugzwang_runtime.cognition.resume import resume_decision
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database

SNAPSHOT_SCHEMA = "zgw.cognitive-snapshot/v1"

_SECRET_KEY_NAMES = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "authorization",
    "bearer",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        record = cast(dict[Any, Any], value)
        result: dict[str, Any] = {}
        for key, item in record.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if (
                normalized in _SECRET_KEY_NAMES
                or normalized.endswith("_key")
                or "password" in normalized
                or normalized.startswith("authorization")
            ):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in cast(list[Any], value)]
    return value


def build_snapshot(
    database: Database,
    cas: ContentAddressedStore,
    decision_id: str,
) -> dict[str, Any]:
    """Export one decision to a redacted causal snapshot (post-hoc, read-only)."""
    journal = CognitionJournal(database)
    from zugzwang_runtime.cognition.session import cas_artifact_loader

    plan = resume_decision(
        journal,
        decision_id,
        state_loader=_snapshot_state_loader(journal, cas),
        payload_loader=cas_artifact_loader(cas),
    )
    report = audit_decision(journal, cas, decision_id)
    exported = export_report(report)
    focus = _decision_focus(journal, decision_id)
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "decision_id": decision_id,
        "status": plan.status,
        "selected_action": plan.selected_action,
        "real_state": {
            "status": plan.status,
            "selected_action": plan.selected_action,
            "operations_settled": plan.operations_settled,
            "operations_open": plan.operations_open,
            "exposure_watermark": plan.exposure_watermark,
        },
        "focus": focus,
        "next_round_ordinal": plan.next_round_ordinal,
        "operations_settled": plan.operations_settled,
        "operations_open": plan.operations_open,
        "exposure_watermark": plan.exposure_watermark,
        "budget_balance": plan.budget_balance,
        "eligible_memories": _eligible_memories(journal, decision_id),
        "transcript": [
            {
                "exposure_sequence": entry["exposure_sequence"],
                "kind": entry["kind"],
                "node_id": entry["node_id"],
                "operation_id": entry["operation_id"],
                "semantic_hash": entry["semantic_hash"],
            }
            for entry in plan.transcript
        ],
        "nodes": [
            {
                "node_id": node["node_id"],
                "depth_plies": node["depth_plies"],
                "fen": node["fen"],
            }
            for node in plan.nodes
        ],
        "audit": exported,
        "mode": "post_hoc",
        "engine": None,
    }
    return _redact(snapshot)


def _snapshot_state_loader(
    journal: CognitionJournal, cas: ContentAddressedStore
):
    """Restore FENs for the snapshot from the durable state artifacts."""
    from zugzwang_chess.environment.standard import StandardChessEnvironment
    from zugzwang_core.domain.artifacts import ArtifactPayload
    from zugzwang_runtime.cognition.session import cas_artifact_loader

    environment = StandardChessEnvironment()
    loader = cas_artifact_loader(cas)

    def load(state_key: str) -> Any:
        with journal.connect() as conn:
            import sqlalchemy as sa

            row = conn.execute(
                sa.text(
                    "SELECT state_artifact_id FROM cb_state_snapshots "
                    "WHERE state_key = :k"
                ),
                {"k": state_key},
            ).fetchone()
        if row is None:
            return None
        data = loader(row[0])
        if data is None:
            return None
        return environment.restore(
            ArtifactPayload(
                media_type="application/x-zugzwang-chess-state+json", data=data
            )
        )

    return load


def _eligible_memories(
    journal: CognitionJournal, decision_id: str
) -> list[dict[str, Any]]:
    """Eligible memories bound to THIS decision (TEST-052 direction).

    Reads the decision's own memory binding, then lists what the eligibility
    policy actually admitted — never invented, never a constant.
    """
    import sqlalchemy as sa

    with journal.connect() as conn:
        binding = conn.execute(
            sa.text(
                "SELECT memory_snapshot_id FROM cb_decisions WHERE decision_id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
    if binding is None or binding[0] is None:
        return []
    snapshot_id = str(binding[0])
    from zugzwang_runtime.cognition.memory import ScopedMemoryStore

    store = ScopedMemoryStore.__new__(ScopedMemoryStore)
    store._database = journal._database  # noqa: SLF001 — same-package reader
    recalled = store.recall(
        snapshot_id=snapshot_id,
        scope_kind="episode",
        scope_owner_id="",
        perspective="neutral",
    )
    return [
        {"memory_id": item.memory_id, "eligibility_reason": item.eligibility_reason}
        for item in recalled.items
    ] + [
        {"memory_id": item.memory_id, "eligibility_reason": "evaluative-separate"}
        for item in recalled.evaluative
    ]


def _decision_focus(journal: CognitionJournal, decision_id: str) -> dict[str, Any]:
    """Focus node (first bound) vs real decision state (§38.11)."""
    nodes = journal.bound_node_ids(decision_id)
    return {"node_id": nodes[0] if nodes else None, "bound_nodes": nodes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="workspace state.db")
    parser.add_argument("--cas", type=Path, required=True, help="workspace CAS root")
    parser.add_argument("--decision", required=True, help="decision id to export")
    parser.add_argument("--out", type=Path, required=True, help="cognitive.json output")
    args = parser.parse_args(argv)
    # The source database is NEVER opened read-write: a query-only handle
    # that applies no journal_mode/synchronous PRAGMAs (ZGW-0101; the old
    # wal_policy="ephemeral" open applied journal_mode=DELETE to the SOURCE).
    database = Database(args.db, wal_policy="enforce", read_only=True)
    database.open()
    cas = ContentAddressedStore(args.cas)
    snapshot = build_snapshot(database, cas, args.decision)
    args.out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out} ({len(json.dumps(snapshot))} bytes)")
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
