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
    plan = resume_decision(journal, decision_id)
    report = audit_decision(journal, cas, decision_id)
    exported = export_report(report)
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "decision_id": decision_id,
        "status": plan.status,
        "selected_action": plan.selected_action,
        "next_round_ordinal": plan.next_round_ordinal,
        "operations_settled": plan.operations_settled,
        "operations_open": plan.operations_open,
        "exposure_watermark": plan.exposure_watermark,
        "budget_balance": plan.budget_balance,
        "audit": exported,
        "mode": "post_hoc",
        "engine": None,
    }
    return _redact(snapshot)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="workspace state.db")
    parser.add_argument("--cas", type=Path, required=True, help="workspace CAS root")
    parser.add_argument("--decision", required=True, help="decision id to export")
    parser.add_argument("--out", type=Path, required=True, help="cognitive.json output")
    args = parser.parse_args(argv)
    database = Database(args.db, wal_policy="ephemeral")
    database.open()
    cas = ContentAddressedStore(args.cas)
    snapshot = build_snapshot(database, cas, args.decision)
    args.out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out} ({len(json.dumps(snapshot))} bytes)")
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
