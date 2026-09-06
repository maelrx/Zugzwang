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
from sqlalchemy.exc import IntegrityError

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
_CONTENT_HASH_RE = __import__("re").compile(r"^[0-9a-f]{64}$")
_EVALUATIVE_EPISTEMICS = frozenset({"model_assessment"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


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
    """Typed retrieval answer: facts plus a separate evaluative section.

    Evaluative notes (model assessments) never ride ``items`` as facts —
    they surface in ``evaluative`` with authorship (TEST-052).
    """

    items: list[RecalledItem] = field(default_factory=list["RecalledItem"])
    evaluative: list[RecalledItem] = field(default_factory=list["RecalledItem"])
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
        if not _CONTENT_HASH_RE.fullmatch(content_hash):
            raise MemoryError(
                "INVALID_ARGUMENTS",
                "content_hash must be a 64-hex sha256; a zero/placeholder hash is refused",
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
        kind: str | None = None,
        perspective: str | None = None,
        payload_artifact_id: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        """A change produces a NEW revision; the old row is never rewritten
        (TEST-043). A changed premise marks needs_review (TEST-048). Only
        presentation/content fields are revisable — identity (logical id,
        origin, scope, partition, sources) never changes across revisions."""
        for label, value in (("kind", kind), ("perspective", perspective)):
            if value is not None and not value:
                raise MemoryError("INVALID_ARGUMENTS", f"empty revisable field {label!r}")
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
                prev_kind,
                epistemic,
                origin,
                scope_kind,
                owner,
                partition,
                prev_perspective,
                run_id,
                episode_id,
                prev_payload,
                prev_hash,
                manifest,
                sequence,
            ) = row
            conn.commit()
        merged: dict[str, Any] = {
            "kind": prev_kind,
            "epistemic_status": epistemic,
            "origin_class": origin,
            "scope_kind": scope_kind,
            "scope_owner_id": owner,
            "partition_name": partition,
            "perspective": prev_perspective,
            "source_run_id": run_id,
            "source_episode_id": episode_id,
            "payload_artifact_id": prev_payload,
            "content_hash": prev_hash,
            "source_manifest_artifact_id": manifest,
            "created_sequence": int(sequence) + 1,
        }
        if kind is not None:
            merged["kind"] = kind
        if perspective is not None:
            merged["perspective"] = perspective
        if payload_artifact_id is not None:
            merged["payload_artifact_id"] = payload_artifact_id
        if content_hash is not None:
            merged["content_hash"] = content_hash
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
            kind=str(merged["kind"]),
            epistemic_status=str(merged["epistemic_status"]),
            origin_class=str(merged["origin_class"]),
            scope_kind=str(merged["scope_kind"]),
            scope_owner_id=str(merged["scope_owner_id"]),
            partition_name=str(merged["partition_name"]),
            perspective=str(merged["perspective"]),
            payload_artifact_id=str(merged["payload_artifact_id"]),
            content_hash=str(merged["content_hash"]),
            source_manifest_artifact_id=str(merged["source_manifest_artifact_id"]),
            source_run_id=merged["source_run_id"],
            source_episode_id=merged["source_episode_id"],
            created_sequence=int(merged["created_sequence"]),
            validity_status=validity,
        )

    def mark_validity(self, memory_id: str, validity: str) -> None:
        """Validity transitions append a superseding revision, never an UPDATE.

        Single connection: the latest revision is read and the successor
        inserted atomically, so concurrent markers cannot collide on
        UNIQUE(logical_memory_id, revision). Integrity conflicts surface as
        MemoryError, never raw DB errors.
        """
        if validity not in _VALIDITY:
            raise MemoryError("INVALID_ARGUMENTS", f"unknown validity {validity!r}")
        with self._connect() as conn:
            latest = conn.execute(
                sa.text(
                    "SELECT logical_memory_id, revision FROM cb_memory_items "
                    "WHERE logical_memory_id = "
                    "(SELECT logical_memory_id FROM cb_memory_items WHERE memory_id = :id) "
                    "ORDER BY revision DESC LIMIT 1"
                ),
                {"id": memory_id},
            ).fetchone()
            if latest is None:
                raise MemoryError("SEMANTICS_MISMATCH", f"unknown memory {memory_id!r}")
            logical, max_revision = latest[0], int(latest[1])
            new_id = f"{logical}-r{int(max_revision) + 1}"
            taken = conn.execute(
                sa.text("SELECT 1 FROM cb_memory_items WHERE memory_id = :new_id"),
                {"new_id": new_id},
            ).fetchone()
            if taken is not None:
                raise MemoryError(
                    "STATE_REPLAY_MISMATCH",
                    f"successor id {new_id!r} already exists; revise explicitly",
                )
            try:
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
                        ":created_at FROM cb_memory_items "
                        "WHERE logical_memory_id = :logical ORDER BY revision DESC LIMIT 1"
                    ),
                    {
                        "new_id": new_id,
                        "logical": logical,
                        "revision": int(max_revision) + 1,
                        "validity": validity,
                        "created_at": self._clock(),
                    },
                )
            except IntegrityError as exc:
                raise MemoryError(
                    "STATE_REPLAY_MISMATCH",
                    f"concurrent validity transition for {logical!r}",
                ) from exc
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
            snap = conn.execute(
                sa.text(
                    "SELECT status, partition_name FROM cb_memory_snapshots WHERE snapshot_id = :id"
                ),
                {"id": snapshot_id},
            ).fetchone()
            if snap is None:
                raise MemoryError("SEMANTICS_MISMATCH", f"unknown snapshot {snapshot_id!r}")
            snap_status, snap_partition = snap[0], snap[1]
            if snap_status not in {"DRAFT", "SEALED"}:
                raise MemoryError("SEMANTICS_MISMATCH", f"bad snapshot {snapshot_id!r}")
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
        evaluative: list[RecalledItem] = []
        superseded: list[str] = []
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
                snapshot_partition=str(snap_partition),
                validity=validity,
                kind=kind,
                epistemic=epistemic,
                scope_kind=scope_kind,
                scope_owner_id=scope_owner_id,
                perspective=perspective,
                item_perspective=str(item_perspective),
                kinds=kinds,
            )
            if reason is None:
                continue
            item = RecalledItem(
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
            if reason == "eligible-evaluative-separate-section":
                evaluative.append(item)
            else:
                if validity == "superseded":
                    superseded.append(memory_id)
                items.append(item)
            if len(items) + len(evaluative) >= limit:
                break
        return RecallResult(
            items=items,
            evaluative=evaluative,
            snapshot_id=snapshot_id,
            policy_hash=policy_hash,
        )

    def _eligibility(
        self,
        *,
        item_scope: str,
        owner: str,
        partition: str,
        snapshot_partition: str = "development",
        validity: str = "active",
        kind: str = "note",
        epistemic: str = "formal_fact",
        scope_kind: str,
        scope_owner_id: str,
        perspective: str,
        item_perspective: str,
        kinds: frozenset[str] | None,
    ) -> str | None:
        # Gate ORDER (ZGW-0101): scope → validity → kind → perspective →
        # partition → epistemic. NO branch returns early: a test-partition
        # note passes the SAME validity/kind/epistemic gates as any other
        # (TEST-047 is isolation, not exemption).
        # 1. Scope gate: a note outside the querying scope never surfaces,
        # however similar (TEST-044).
        if item_scope != scope_kind or owner != scope_owner_id:
            return None
        # 2. Quarantined/contradicted notes are ineligible until reviewed —
        # including inside a test snapshot (a quarantine is not washed by
        # partition context).
        if validity in {"quarantined", "contradicted"}:
            return None
        # 3. Kind filter applies everywhere.
        if kinds is not None and kind not in kinds:
            return None
        # 4. Perspective gate: a neutral query admits every perspective; a
        # positioned query admits only matching or neutral notes.
        if perspective != "neutral" and item_perspective not in {perspective, "neutral"}:
            return None
        # 5. Partition isolation is symmetric (TEST-047): test notes recall
        # only inside test snapshots, and non-test notes never surface inside
        # a test snapshot.
        partition_isolated = partition == "test" or snapshot_partition == "test"
        if partition_isolated and partition != snapshot_partition:
            return None
        # 6. Epistemic separation BEFORE the partition reason: assessments
        # stay evaluations in every partition (INV-07).
        if epistemic in _EVALUATIVE_EPISTEMICS:
            return "eligible-evaluative-separate-section"
        if partition_isolated:
            return "eligible-test-scope-only"
        return "eligible-scope-partition-validity"

    # -- restore ------------------------------------------------------------------

    _RESTORE_REQUIRED_FIELDS = (
        "memory_id",
        "logical_memory_id",
        "origin_class",
        "content_hash",
        "payload_artifact_id",
        "source_manifest_artifact_id",
    )

    def restore_notes(self, records: list[dict[str, Any]]) -> int:
        """Seed/import path: every record passes the same gates as writes.

        ZGW-0101: metadata is never invented. A record missing required
        provenance (origin, content hash, artifact refs) is REJECTED with an
        explicit reason — never defaulted to endogenous/neutral/hash-zero —
        and an unknown origin is refused, not silently accepted. The recorded
        validity travels with the note (a quarantined note restores
        quarantined), so restoration cannot reactivate reviewed-out items
        (TEST-045 'também na restauração').
        """
        restored = 0
        for record in records:
            # Provenance gate FIRST: a contaminated or unknown origin is the
            # headline rejection, before any shape complaint.
            origin = str(record.get("origin_class", ""))
            if origin in _CONTAMINATED_ORIGINS:
                raise MemoryError(
                    "SOURCE_NOT_ALLOWED",
                    f"origin {origin!r} is not admissible as memory",
                )
            if not origin:
                raise MemoryError(
                    "INVALID_ARGUMENTS",
                    f"restore record {record.get('memory_id', '?')!r} is missing "
                    "'origin_class'; unknown provenance is rejected, not invented",
                )
            if origin not in _ORIGIN:
                raise MemoryError(
                    "SOURCE_NOT_ALLOWED",
                    f"restore record {record.get('memory_id', '?')!r} carries unknown "
                    f"origin {origin!r}; quarantine or reject it explicitly",
                )
            for field_name in self._RESTORE_REQUIRED_FIELDS:
                value = record.get(field_name)
                if value is None or (isinstance(value, str) and not value):
                    raise MemoryError(
                        "INVALID_ARGUMENTS",
                        f"restore record {record.get('memory_id', '?')!r} is missing "
                        f"{field_name!r}; unknown provenance is rejected, not invented",
                    )
            origin = str(record["origin_class"])
            raw_revision: Any = record.get("revision", 1)
            raw_sequence: Any = record.get("created_sequence", 0)
            self.write_note(
                memory_id=str(record["memory_id"]),
                logical_memory_id=str(record["logical_memory_id"]),
                revision=int(raw_revision),
                kind=str(record["kind"]),
                epistemic_status=str(record["epistemic_status"]),
                origin_class=origin,
                scope_kind=str(record["scope_kind"]),
                scope_owner_id=str(record["scope_owner_id"]),
                partition_name=str(record["partition_name"]),
                perspective=str(record["perspective"]),
                payload_artifact_id=str(record["payload_artifact_id"]),
                content_hash=str(record["content_hash"]),
                source_manifest_artifact_id=str(record["source_manifest_artifact_id"]),
                source_run_id=_optional_str(record.get("source_run_id")),
                source_episode_id=_optional_str(record.get("source_episode_id")),
                created_sequence=int(raw_sequence),
                validity_status=str(record.get("validity_status", "active")),
            )
            restored += 1
        return restored

    # -- legacy -----------------------------------------------------------------

    def read_legacy_note(self, record: dict[str, Any]) -> dict[str, Any]:
        """Legacy reader: unknown fields are marked, origin never invented."""
        known = {
            "memory_id",
            "logical_memory_id",
            "revision",
            "kind",
            "epistemic_status",
            "validity_status",
            "origin_class",
            "scope_kind",
            "scope_owner_id",
            "partition_name",
            "perspective",
            "content_hash",
            "payload_artifact_id",
            "source_run_id",
            "source_episode_id",
        }
        out: dict[str, Any] = {key: record[key] for key in known if key in record}
        unknown = sorted(key for key in record if key not in known and key != "origin")
        if unknown:
            out["unknown_fields"] = unknown
        out["origin"] = record.get("origin", "unknown-unrecorded")
        return out
