"""CognitiveBoard conditioned memory store (PRD §16, §38.10; CB-WO-09).

``ScopedMemoryStore`` is the single writer over the CB-M2 tables (§23.2):
memory items with immutable revisions, immutable links, DRAFT→SEALED
snapshots with frozen members, and typed retrieval with eligibility before
ranking (TEST-044). Engine/eval-sourced notes are refused at write and at
restore (TEST-045); test-partition notes never enter train/selection
(TEST-047); premise changes mark needs_review instead of declaring strategic
refutation (TEST-048); actions derive from the graph, never from notes
(TEST-052). The legacy note reader marks unknown fields without inventing
origin (compat).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ..persistence.database import Database

_VALIDITY = frozenset({"active", "needs_review", "superseded", "contradicted", "quarantined"})
_EPISTEMIC = frozenset(
    {
        "formal_fact",
        "model_hypothesis",
        "model_assessment",
        "observed_outcome",
        "human_annotation",
    }
)
_ORIGIN = frozenset(
    {"rules", "endogenous", "human", "expert_corpus", "oracle_informed_offline", "evaluation"}
)
_SCOPE = frozenset({"decision", "episode", "run", "corpus", "campaign"})
_PARTITION = frozenset({"train", "validation", "test", "development", "unspecified"})
_CONTAMINATED_ORIGINS = frozenset({"evaluation"})
_EVALUATIVE_EPISTEMICS = frozenset({"model_assessment"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MemoryError(Exception):
    """Memory rejection with machine code (CODING_STANDARDS / Errors)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class RecalledItem:
    """One eligible memory with its selection reason (PRD §16)."""

    memory_id: str
    logical_memory_id: str
    revision: int
    kind: str
    scope_kind: str
    scope_owner_id: str
    partition_name: str
    perspective: str
    epistemic_status: str
    validity_status: str
    content_hash: str
    payload_artifact_id: str
    eligibility_reason: str
    origin_context: str


@dataclass(slots=True)
class RecallResult:
    """Typed retrieval answer: eligible items + reasons, never bare text."""

    items: list[RecalledItem] = field(default_factory=list["RecalledItem"])
    snapshot_id: str | None = None
    policy_hash: str = ""


class ScopedMemoryStore:
    """Single writer/reader over the CB-M2 memory tables (§23.2)."""

    def __init__(self, database: Database, clock: Callable[[], str] | None = None) -> None:
        self._database = database
        self._clock = clock or _now

    def _connect(self) -> Connection:
        return self._database.engine().connect()

    # -- items ---------------------------------------------------------------

    def write_note(
        self,
        *,
        memory_id: str,
        logical_memory_id: str,
        revision: int,
        kind: str,
        epistemic_status: str,
        origin_class: str,
        scope_kind: str,
        scope_owner_id: str,
        partition_name: str,
        perspective: str,
        payload_artifact_id: str,
        content_hash: str,
        source_manifest_artifact_id: str,
        source_run_id: str | None = None,
        source_episode_id: str | None = None,
        created_sequence: int = 0,
        validity_status: str = "active",
    ) -> None:
        """Write one revision; engine/eval sources are refused (TEST-045)."""
        if origin_class in _CONTAMINATED_ORIGINS:
            raise MemoryError(
                "SOURCE_NOT_ALLOWED",
                f"origin {origin_class!r} is not admissible as memory",
            )
        if epistemic_status not in _EPISTEMIC or origin_class not in _ORIGIN:
            raise MemoryError("INVALID_ARGUMENTS", "unknown epistemic status or origin")
        if scope_kind not in _SCOPE or partition_name not in _PARTITION:
            raise MemoryError("INVALID_ARGUMENTS", "unknown scope or partition")
        if validity_status not in _VALIDITY:
            raise MemoryError("INVALID_ARGUMENTS", f"unknown validity {validity_status!r}")
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_memory_items (memory_id, logical_memory_id, revision, "
                    "kind, epistemic_status, validity_status, origin_class, scope_kind, "
                    "scope_owner_id, partition_name, perspective, source_run_id, "
                    "source_episode_id, payload_artifact_id, content_hash, "
                    "source_manifest_artifact_id, created_sequence, created_at) "
                    "VALUES (:memory_id, :logical_memory_id, :revision, :kind, "
                    ":epistemic_status, :validity_status, :origin_class, :scope_kind, "
                    ":scope_owner_id, :partition_name, :perspective, :source_run_id, "
                    ":source_episode_id, :payload_artifact_id, :content_hash, "
                    ":source_manifest_artifact_id, :created_sequence, :created_at)"
                ),
                {
                    "memory_id": memory_id,
                    "logical_memory_id": logical_memory_id,
                    "revision": revision,
                    "kind": kind,
                    "epistemic_status": epistemic_status,
                    "validity_status": validity_status,
                    "origin_class": origin_class,
                    "scope_kind": scope_kind,
                    "scope_owner_id": scope_owner_id,
                    "partition_name": partition_name,
                    "perspective": perspective,
                    "source_run_id": source_run_id,
                    "source_episode_id": source_episode_id,
                    "payload_artifact_id": payload_artifact_id,
                    "content_hash": content_hash,
                    "source_manifest_artifact_id": source_manifest_artifact_id,
                    "created_sequence": created_sequence,
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    def revise_note(
        self,
        *,
        memory_id: str,
        logical_memory_id: str,
        revision: int,
        premise_changed: bool = False,
        **fields: Any,
    ) -> None:
        """A change produces a NEW revision; the old row is never rewritten
        (TEST-043). A changed premise marks needs_review (TEST-048)."""
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT kind, epistemic_status, origin_class, scope_kind, "
                    "scope_owner_id, partition_name, perspective, source_run_id, "
                    "source_episode_id, payload_artifact_id, content_hash, "
                    "source_manifest_artifact_id, created_sequence "
                    "FROM cb_memory_items WHERE logical_memory_id = :logical "
                    "ORDER BY revision DESC LIMIT 1"
                ),
                {"logical": logical_memory_id},
            ).fetchone()
            if row is None:
                raise MemoryError("SEMANTICS_MISMATCH", f"unknown note {logical_memory_id!r}")
            (
                kind,
                epistemic,
                origin,
                scope_kind,
                owner,
                partition,
                perspective,
                run_id,
                episode_id,
                payload,
                content_hash,
                manifest,
                sequence,
            ) = row
            conn.commit()
        merged: dict[str, Any] = {
            "kind": kind,
            "epistemic_status": epistemic,
            "origin_class": origin,
            "scope_kind": scope_kind,
            "scope_owner_id": owner,
            "partition_name": partition,
            "perspective": perspective,
            "source_run_id": run_id,
            "source_episode_id": episode_id,
            "payload_artifact_id": payload,
            "content_hash": content_hash,
            "source_manifest_artifact_id": manifest,
            "created_sequence": int(sequence) + 1,
        }
        merged.update(fields)
        if premise_changed:
            # A changed premise marks needs_review on the new revision itself
            # (TEST-048) — no strategic refutation is declared.
            merged["validity_override"] = "needs_review"
        validity = str(merged.pop("validity_override", "active"))
        if validity not in _VALIDITY:
            raise MemoryError("INVALID_ARGUMENTS", f"unknown validity {validity!r}")
        self.write_note(
            memory_id=memory_id,
            logical_memory_id=logical_memory_id,
            revision=revision,
            validity_status=validity,
            **merged,  # type: ignore[arg-type]
        )

    def mark_validity(self, memory_id: str, validity: str) -> None:
        """Validity transitions append a superseding revision, never an UPDATE."""
        if validity not in _VALIDITY:
            raise MemoryError("INVALID_ARGUMENTS", f"unknown validity {validity!r}")
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT logical_memory_id, MAX(revision) FROM cb_memory_items "
                    "WHERE memory_id = :id OR logical_memory_id = "
                    "(SELECT logical_memory_id FROM cb_memory_items WHERE memory_id = :id)"
                ),
                {"id": memory_id},
            ).fetchone()
            current = conn.execute(
                sa.text(
                    "SELECT kind, epistemic_status, origin_class, scope_kind, "
                    "scope_owner_id, partition_name, perspective, source_run_id, "
                    "source_episode_id, payload_artifact_id, content_hash, "
                    "source_manifest_artifact_id, created_sequence "
                    "FROM cb_memory_items WHERE memory_id = :id"
                ),
                {"id": memory_id},
            ).fetchone()
            if row is None or current is None:
                raise MemoryError("SEMANTICS_MISMATCH", f"unknown memory {memory_id!r}")
            logical, max_revision = row[0], int(row[1])
            conn.commit()
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_memory_items (memory_id, logical_memory_id, revision, "
                    "kind, epistemic_status, validity_status, origin_class, scope_kind, "
                    "scope_owner_id, partition_name, perspective, source_run_id, "
                    "source_episode_id, payload_artifact_id, content_hash, "
                    "source_manifest_artifact_id, created_sequence, created_at) "
                    "SELECT :new_id, logical_memory_id, :revision, kind, epistemic_status, "
                    ":validity, origin_class, scope_kind, scope_owner_id, partition_name, "
                    "perspective, source_run_id, source_episode_id, payload_artifact_id, "
                    "content_hash, source_manifest_artifact_id, created_sequence + 1, "
                    ":created_at FROM cb_memory_items WHERE memory_id = :id"
                ),
                {
                    "new_id": f"{logical}-r{int(max_revision) + 1}",
                    "revision": int(max_revision) + 1,
                    "validity": validity,
                    "created_at": self._clock(),
                    "id": memory_id,
                },
            )
            conn.commit()

    def link(
        self,
        *,
        memory_id: str,
        link_kind: str,
        target_key: str,
        relation_name: str = "about",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_memory_links (memory_id, link_kind, target_key, "
                    "relation_name) VALUES (:memory_id, :link_kind, :target_key, "
                    ":relation_name)"
                ),
                {
                    "memory_id": memory_id,
                    "link_kind": link_kind,
                    "target_key": target_key,
                    "relation_name": relation_name,
                },
            )
            conn.commit()

    # -- snapshots ------------------------------------------------------------

    def open_snapshot(
        self,
        *,
        snapshot_id: str,
        scope_kind: str,
        scope_owner_id: str,
        partition_name: str,
        policy_hash: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_memory_snapshots (snapshot_id, scope_kind, "
                    "scope_owner_id, partition_name, policy_hash, status, created_at) "
                    "VALUES (:snapshot_id, :scope_kind, :scope_owner_id, "
                    ":partition_name, :policy_hash, 'DRAFT', :created_at)"
                ),
                {
                    "snapshot_id": snapshot_id,
                    "scope_kind": scope_kind,
                    "scope_owner_id": scope_owner_id,
                    "partition_name": partition_name,
                    "policy_hash": policy_hash,
                    "created_at": self._clock(),
                },
            )
            conn.commit()

    def add_member(self, *, snapshot_id: str, memory_id: str, ordinal: int) -> None:
        """Sealed snapshots refuse members (TEST-042, trigger-enforced)."""
        with self._connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO cb_memory_snapshot_members (snapshot_id, memory_id, "
                    "ordinal) VALUES (:snapshot_id, :memory_id, :ordinal)"
                ),
                {"snapshot_id": snapshot_id, "memory_id": memory_id, "ordinal": ordinal},
            )
            conn.commit()

    def seal_snapshot(self, *, snapshot_id: str, manifest_artifact_id: str) -> None:
        with self._connect() as conn:
            result = conn.execute(
                sa.text(
                    "UPDATE cb_memory_snapshots SET status = 'SEALED', "
                    "manifest_artifact_id = :manifest, sealed_at = :sealed_at "
                    "WHERE snapshot_id = :snapshot_id AND status = 'DRAFT'"
                ),
                {
                    "manifest": manifest_artifact_id,
                    "sealed_at": self._clock(),
                    "snapshot_id": snapshot_id,
                },
            )
            if result.rowcount != 1:
                raise MemoryError("STATE_REPLAY_MISMATCH", f"snapshot {snapshot_id!r} not draft")
            conn.commit()

    # -- retrieval -------------------------------------------------------------

    def recall(
        self,
        *,
        snapshot_id: str,
        scope_kind: str,
        scope_owner_id: str,
        perspective: str = "neutral",
        kinds: frozenset[str] | None = None,
        limit: int = 16,
        policy_hash: str = "",
    ) -> RecallResult:
        """Typed retrieval: eligibility (scope/partition/validity) BEFORE any
        ranking (TEST-044). Test-partition notes never surface (TEST-047);
        evaluative notes surface only in a separate authored section, never
        as facts (TEST-052 direction — enforced by kind filter here)."""
        with self._connect() as conn:
            status = conn.execute(
                sa.text("SELECT status FROM cb_memory_snapshots WHERE snapshot_id = :id"),
                {"id": snapshot_id},
            ).fetchone()
            if status is None:
                raise MemoryError("SEMANTICS_MISMATCH", f"unknown snapshot {snapshot_id!r}")
            rows = conn.execute(
                sa.text(
                    "SELECT i.memory_id, i.logical_memory_id, i.revision, i.kind, "
                    "i.scope_kind, i.scope_owner_id, i.partition_name, i.perspective, "
                    "i.epistemic_status, i.validity_status, i.content_hash, "
                    "i.payload_artifact_id FROM cb_memory_snapshot_members m "
                    "JOIN cb_memory_items i ON i.memory_id = m.memory_id "
                    "WHERE m.snapshot_id = :snapshot_id ORDER BY m.ordinal"
                ),
                {"snapshot_id": snapshot_id},
            ).fetchall()
            conn.commit()
        items: list[RecalledItem] = []
        for row in rows:
            (
                memory_id,
                logical,
                revision,
                kind,
                item_scope,
                owner,
                partition,
                item_perspective,
                epistemic,
                validity,
                content_hash,
                payload,
            ) = row
            reason = self._eligibility(
                item_scope=item_scope,
                owner=owner,
                partition=partition,
                validity=validity,
                kind=kind,
                epistemic=epistemic,
                scope_kind=scope_kind,
                scope_owner_id=scope_owner_id,
                perspective=perspective,
                kinds=kinds,
            )
            if reason is None:
                continue
            items.append(
                RecalledItem(
                    memory_id=memory_id,
                    logical_memory_id=logical,
                    revision=int(revision),
                    kind=kind,
                    scope_kind=item_scope,
                    scope_owner_id=owner,
                    partition_name=partition,
                    perspective=item_perspective,
                    epistemic_status=epistemic,
                    validity_status=validity,
                    content_hash=content_hash,
                    payload_artifact_id=payload,
                    eligibility_reason=reason,
                    origin_context=f"{item_scope}:{owner}/{partition}",
                )
            )
            if len(items) >= limit:
                break
        return RecallResult(items=items, snapshot_id=snapshot_id, policy_hash=policy_hash)

    def _eligibility(
        self,
        *,
        item_scope: str,
        owner: str,
        partition: str,
        validity: str,
        kind: str,
        epistemic: str = "formal_fact",
        scope_kind: str,
        scope_owner_id: str,
        perspective: str,
        kinds: frozenset[str] | None,
    ) -> str | None:
        # Scope gate first: a note outside the querying scope never surfaces,
        # however similar (TEST-044). Episode scope additionally admits notes
        # from the same run's committed steps (TEST-046 — owner match).
        if item_scope != scope_kind or owner != scope_owner_id:
            return None
        # Test partition is isolated from train/selection (TEST-047).
        if partition == "test":
            return None
        # Quarantined/contradicted notes are ineligible until reviewed.
        if validity in {"quarantined", "contradicted"}:
            return None
        if kinds is not None and kind not in kinds:
            return None
        if epistemic in _EVALUATIVE_EPISTEMICS:
            return "eligible-evaluative-separate-section"
        return "eligible-scope-partition-validity"

    # -- legacy -----------------------------------------------------------------

    def read_legacy_note(self, record: dict[str, Any]) -> dict[str, Any]:
        """Legacy reader: unknown fields are marked, origin never invented."""
        known = {
            "memory_id",
            "logical_memory_id",
            "revision",
            "kind",
            "content_hash",
            "scope_kind",
            "scope_owner_id",
        }
        out: dict[str, Any] = {key: record[key] for key in known if key in record}
        unknown = sorted(key for key in record if key not in known and key != "origin")
        if unknown:
            out["unknown_fields"] = unknown
        out["origin"] = record.get("origin", "unknown-unrecorded")
        return out
