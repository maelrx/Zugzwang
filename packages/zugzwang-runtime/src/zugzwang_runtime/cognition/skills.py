"""CognitiveBoard skill registry (PRD §38.13; CB-WO-12).

``SkillRegistry`` is the single writer over the CB-M3 tables (§23.2):
version pipeline CANDIDATE→APPROVED/REJECTED (approval mints the approved
row — versions are never updated), DRAFT→SEALED sets with approved-only
members, and activation by allowlist. Skill text is data without authority:
it never alters capabilities nor executes commands (TEST-049); a scientific
set never admits a candidate version (TEST-050); sealed sets refuse change
while the condition hash stands (TEST-051). Decisions record their skill set
for paired ablation with context control.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ..persistence.database import Database

_ALLOWED_ORIGINS = frozenset(
    {"proposed_procedure", "human", "endogenous", "oracle_informed_offline"}
)

#: Capability names a skill may request. Anything outside this allowlist —
#: including anything the skill TEXT asks for — is refused (TEST-049).
ALLOWED_CAPABILITIES = frozenset({"observe", "inspect", "expand", "compare", "recall"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SkillError(Exception):
    """Skill rejection with machine code (CODING_STANDARDS / Errors)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ActivationResult:
    """Authorized activation of one skill version for a decision."""

    skill_version_id: str
    skill_id: str
    version: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)


class SkillRegistry:
    """Single writer/reader over the CB-M3 skill tables (§23.2)."""

    def __init__(self, database: Database, clock: Callable[[], str] | None = None) -> None:
        self._database = database
        self._clock = clock or _now

    def _connect(self) -> Connection:
        return self._database.engine().connect()

    # -- versions -------------------------------------------------------------

    def propose(
        self,
        *,
        skill_version_id: str,
        skill_id: str,
        version: str,
        content_hash: str,
        payload_artifact_id: str,
        provenance_artifact_id: str,
        origin_class: str = "proposed_procedure",
    ) -> None:
        """Propose a procedure: always enters as CANDIDATE, never approved."""
        if origin_class not in _ALLOWED_ORIGINS:
            raise SkillError("INVALID_ARGUMENTS", f"unknown origin {origin_class!r}")
        with self._connect() as conn:
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_skill_versions (skill_version_id, skill_id, "
                        "version, content_hash, payload_artifact_id, "
                        "provenance_artifact_id, origin_class, status, created_at) "
                        "VALUES (:id, :skill_id, :version, :hash, :payload, "
                        ":provenance, :origin, 'CANDIDATE', :created_at)"
                    ),
                    {
                        "id": skill_version_id,
                        "skill_id": skill_id,
                        "version": version,
                        "hash": content_hash,
                        "payload": payload_artifact_id,
                        "provenance": provenance_artifact_id,
                        "origin": origin_class,
                        "created_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH", f"skill version {skill_version_id!r} exists"
                ) from exc

    def approve(
        self,
        *,
        skill_version_id: str,
        approval_artifact_id: str,
    ) -> str:
        """Approve by minting the release row ``{skill_id}@{version}``.

        Versions are immutable (no UPDATE by trigger): approval copies the
        candidate into an APPROVED release row. The candidate row stays for
        audit; the release id is what joins sealed sets. Returns it.
        """
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT skill_id, version, content_hash, payload_artifact_id, "
                    "provenance_artifact_id, origin_class FROM cb_skill_versions "
                    "WHERE skill_version_id = :id AND status = 'CANDIDATE'"
                ),
                {"id": skill_version_id},
            ).fetchone()
            if row is None:
                raise SkillError("SEMANTICS_MISMATCH", f"no candidate version {skill_version_id!r}")
            skill_id, version, content_hash, payload, provenance, origin = row
            approved_id = f"{skill_id}@{version}#approved"
            release_version = f"{version}+approved"
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_skill_versions (skill_version_id, skill_id, "
                        "version, content_hash, payload_artifact_id, "
                        "provenance_artifact_id, approval_artifact_id, origin_class, "
                        "status, created_at) VALUES (:id, :skill_id, :version, :hash, "
                        ":payload, :provenance, :approval, :origin, 'APPROVED', "
                        ":created_at)"
                    ),
                    {
                        "id": approved_id,
                        "skill_id": skill_id,
                        "version": release_version,
                        "hash": content_hash,
                        "payload": payload,
                        "provenance": provenance,
                        "approval": approval_artifact_id,
                        "origin": origin,
                        "created_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH",
                    f"release {approved_id!r} already exists",
                ) from exc
            return approved_id

    def reject(self, *, skill_version_id: str) -> str:
        """Reject a candidate by minting its REJECTED tombstone row.

        The candidate row itself is immutable (no UPDATE/DELETE by trigger):
        rejection copies it to ``{id}#rejected`` so the pipeline outcome is
        journaled while the proposal stays for audit. Returns the tombstone id.
        """
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT skill_id, version, content_hash, payload_artifact_id, "
                    "provenance_artifact_id, origin_class FROM cb_skill_versions "
                    "WHERE skill_version_id = :id AND status = 'CANDIDATE'"
                ),
                {"id": skill_version_id},
            ).fetchone()
            if row is None:
                raise SkillError("SEMANTICS_MISMATCH", f"no candidate version {skill_version_id!r}")
            skill_id, version, content_hash, payload, provenance, origin = row
            tombstone_id = f"{skill_version_id}#rejected"
            tombstone_version = f"{version}+rejected"
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_skill_versions (skill_version_id, skill_id, "
                        "version, content_hash, payload_artifact_id, "
                        "provenance_artifact_id, origin_class, status, created_at) "
                        "VALUES (:id, :skill_id, :version, :hash, :payload, "
                        ":provenance, :origin, 'REJECTED', :created_at)"
                    ),
                    {
                        "id": tombstone_id,
                        "skill_id": skill_id,
                        "version": tombstone_version,
                        "hash": content_hash,
                        "payload": payload,
                        "provenance": provenance,
                        "origin": origin,
                        "created_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH",
                    f"tombstone {tombstone_id!r} already exists",
                ) from exc
            return tombstone_id

    # -- sets ------------------------------------------------------------------

    def open_set(self, *, skill_set_id: str, policy_hash: str) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_skill_sets (skill_set_id, policy_hash, status, "
                        "created_at) VALUES (:id, :policy, 'DRAFT', :created_at)"
                    ),
                    {
                        "id": skill_set_id,
                        "policy": policy_hash,
                        "created_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH",
                    f"skill set {skill_set_id!r} already exists",
                ) from exc

    def add_member(self, *, skill_set_id: str, skill_version_id: str, ordinal: int) -> None:
        """Only APPROVED versions join DRAFT sets (TEST-050, trigger-enforced)."""
        with self._connect() as conn:
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_skill_set_members (skill_set_id, skill_version_id, "
                        "ordinal) VALUES (:set_id, :version_id, :ordinal)"
                    ),
                    {
                        "set_id": skill_set_id,
                        "version_id": skill_version_id,
                        "ordinal": ordinal,
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH",
                    f"cannot add {skill_version_id!r} to set {skill_set_id!r}",
                ) from exc

    def seal_set(self, *, skill_set_id: str, manifest_artifact_id: str) -> None:
        with self._connect() as conn:
            result = conn.execute(
                sa.text(
                    "UPDATE cb_skill_sets SET status = 'SEALED', manifest_artifact_id = "
                    ":manifest, sealed_at = :sealed_at "
                    "WHERE skill_set_id = :id AND status = 'DRAFT'"
                ),
                {
                    "manifest": manifest_artifact_id,
                    "sealed_at": self._clock(),
                    "id": skill_set_id,
                },
            )
            if result.rowcount != 1:
                raise SkillError("STATE_REPLAY_MISMATCH", f"skill set {skill_set_id!r} not draft")
            conn.commit()

    # -- activation ---------------------------------------------------------------

    def activate(
        self, *, skill_set_id: str, skill_id: str, requested: tuple[str, ...] = ()
    ) -> ActivationResult:
        """Activate one skill from a SEALED set by allowlist (TEST-049).

        The skill TEXT is never consulted: only the allowlisted capability
        names in ``requested`` (intersected with ALLOWED_CAPABILITIES) are
        granted. Anything the text asks for beyond the allowlist is refused.
        """
        with self._connect() as conn:
            status = conn.execute(
                sa.text("SELECT status FROM cb_skill_sets WHERE skill_set_id = :id"),
                {"id": skill_set_id},
            ).fetchone()
            if status is None or status[0] != "SEALED":
                raise SkillError("SEMANTICS_MISMATCH", f"set {skill_set_id!r} not sealed")
            row = conn.execute(
                sa.text(
                    "SELECT v.skill_version_id, v.version FROM cb_skill_set_members m "
                    "JOIN cb_skill_versions v ON v.skill_version_id = m.skill_version_id "
                    "WHERE m.skill_set_id = :set_id AND v.skill_id = :skill_id "
                    "AND v.status = 'APPROVED' ORDER BY m.ordinal LIMIT 1"
                ),
                {"set_id": skill_set_id, "skill_id": skill_id},
            ).fetchone()
        if row is None:
            raise SkillError(
                "SEMANTICS_MISMATCH",
                f"skill {skill_id!r} not in sealed set {skill_set_id!r}",
            )
        granted = tuple(cap for cap in requested if cap in ALLOWED_CAPABILITIES)
        refused = [cap for cap in requested if cap not in ALLOWED_CAPABILITIES]
        if refused:
            raise SkillError(
                "TOOL_NOT_ALLOWED",
                f"capabilities outside the allowlist refused: {refused}",
            )
        return ActivationResult(
            skill_version_id=row[0], skill_id=skill_id, version=row[1], capabilities=granted
        )

    def bind_decision(self, *, decision_id: str, skill_set_id: str) -> None:
        """Record the skill set on the decision for paired ablation context.

        Only SEALED sets bind (§43.2 decision guard); unknown sets and unknown
        decisions fail closed instead of silently no-op'ing.
        """
        with self._connect() as conn:
            status = conn.execute(
                sa.text("SELECT status FROM cb_skill_sets WHERE skill_set_id = :id"),
                {"id": skill_set_id},
            ).fetchone()
            if status is None:
                raise SkillError("SEMANTICS_MISMATCH", f"unknown set {skill_set_id!r}")
            if status[0] != "SEALED":
                raise SkillError("SEMANTICS_MISMATCH", f"set {skill_set_id!r} is not sealed")
            try:
                result = conn.execute(
                    sa.text(
                        "UPDATE cb_decisions SET skill_set_id = :set_id "
                        "WHERE decision_id = :decision_id"
                    ),
                    {"set_id": skill_set_id, "decision_id": decision_id},
                )
                if result.rowcount != 1:
                    raise SkillError("SEMANTICS_MISMATCH", f"unknown decision {decision_id!r}")
                conn.commit()
            except IntegrityError as exc:
                raise SkillError(
                    "STATE_REPLAY_MISMATCH",
                    f"cannot bind {skill_set_id!r} to {decision_id!r}",
                ) from exc
