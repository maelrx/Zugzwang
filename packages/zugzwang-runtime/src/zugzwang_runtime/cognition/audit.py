"""CognitiveBoard end-to-end audit (PRD §38.9; CB-WO-08, TEST-080).

``audit_decision`` rebuilds choice, costs, exposure and limits purely from
the journal rows + CAS objects — no provider, no engine (TEST-058). Every
referenced artifact is hash-verified before its content enters the report
(TEST-054); malformed references never resolve outside the CAS (TEST-053);
the exported report carries no secrets (TEST-059).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

import sqlalchemy as sa

from zugzwang_core.domain.canonical import sha256_hex

from ..artifacts.cas import ContentAddressedStore
from ..persistence.cognition import CognitionJournal

_SECRET_KEYS = frozenset(
    {"access_token", "cookie", "set-cookie", "secret", "client_secret", "api_key", "token"}
)

_ARTIFACT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(slots=True)
class AuditReport:
    """Reconstructed choice, costs, exposure and limits of one decision."""

    decision_id: str
    status: str
    selected_action: str | None
    operations: list[dict[str, Any]]
    observations: int
    exposure_watermark: int
    budget_balance: dict[str, dict[str, int]]
    artifacts_verified: int
    artifacts_failed: list[str]


def validate_artifact_id(value: str) -> bool:
    """A reference that cannot resolve inside the CAS is rejected (TEST-053)."""
    return bool(_ARTIFACT_ID_RE.fullmatch(value))


def redact(value: Any) -> Any:
    """Strip credential-shaped fields from exported structures (TEST-059)."""
    if isinstance(value, dict):
        record = cast(dict[Any, Any], value)
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SECRET_KEYS else redact(item)
            for key, item in record.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in cast(list[Any], value)]
    return value


def audit_decision(
    journal: CognitionJournal,
    cas: ContentAddressedStore,
    decision_id: str,
    *,
    verify_payloads: bool = True,
) -> AuditReport:
    """Rebuild the decision's choice, costs, exposure and limits."""
    with journal.connect() as conn:
        decision = conn.execute(
            sa.text("SELECT status, selected_action FROM cb_decisions WHERE decision_id = :id"),
            {"id": decision_id},
        ).fetchone()
        if decision is None:
            from ..persistence.cognition import DecisionJournalError

            raise DecisionJournalError("SEMANTICS_MISMATCH", f"unknown decision {decision_id!r}")
        operations = conn.execute(
            sa.text(
                "SELECT operation_id, tool_name, status, error_code, result_artifact_id "
                "FROM cb_tool_operations WHERE decision_id = :id ORDER BY created_at"
            ),
            {"id": decision_id},
        ).fetchall()
        observations = conn.execute(
            sa.text(
                "SELECT COUNT(*), COALESCE(MAX(exposure_sequence), 0) FROM cb_observations "
                "WHERE decision_id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
        conn.commit()
    balance = journal.reconcile_budget(decision_id)

    verified = 0
    failed: list[str] = []
    op_records: list[dict[str, Any]] = []
    for row in operations:
        operation_id, tool_name, status, error_code, result_artifact = (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
        )
        record: dict[str, Any] = {
            "operation_id": operation_id,
            "tool": tool_name,
            "status": status,
            "error_code": error_code,
        }
        if result_artifact is not None and verify_payloads:
            ok, _ = _verify_artifact(cas, result_artifact)
            if ok:
                verified += 1
            else:
                failed.append(result_artifact)
            record["artifact_verified"] = ok
        op_records.append(record)

    return AuditReport(
        decision_id=decision_id,
        status=decision[0],
        selected_action=decision[1],
        operations=op_records,
        observations=int(observations[0]) if observations else 0,
        exposure_watermark=int(observations[1]) if observations else 0,
        budget_balance={unit: dict(values) for unit, values in balance.items()},
        artifacts_verified=verified,
        artifacts_failed=failed,
    )


def _verify_artifact(cas: ContentAddressedStore, artifact_id: str) -> tuple[bool, bytes | None]:
    """Hash-verify one CAS object; corruption fails before exposure (TEST-054)."""
    from zugzwang_core.domain.artifacts import ArtifactRef
    from zugzwang_core.domain.errors import ArtifactError

    if not validate_artifact_id(artifact_id):
        return False, None
    try:
        ref = ArtifactRef.parse(artifact_id)
    except ArtifactError:
        return False, None
    if not cas.exists(ref):
        return False, None
    try:
        payload = cas.get(ref)
    except (ArtifactError, OSError):
        return False, None
    digest = sha256_hex(payload.data)
    if digest != ref.digest.lower():
        return False, None
    return True, payload.data


def export_report(report: AuditReport) -> dict[str, Any]:
    """Redacted exportable form of an audit report (TEST-059)."""
    return redact(
        {
            "decision_id": report.decision_id,
            "status": report.status,
            "selected_action": report.selected_action,
            "operations": report.operations,
            "observations": report.observations,
            "exposure_watermark": report.exposure_watermark,
            "budget_balance": report.budget_balance,
            "artifacts_verified": report.artifacts_verified,
            "artifacts_failed": report.artifacts_failed,
        }
    )
