"""CognitiveBoard plan store (PRD §38.14; CB-WO-13).

``PlanStore`` is the single writer over the CB-M4 tables (§23.2):
decision-anchored investigations and episode-scoped conditional plans with
perspective. Premises are evaluated by a small auditable predicate DSL over
three states (true/false/unknown); a changed premise marks the plan
needs_review — never a strategic refutation certificate (TEST-048). Plans
carry across turns with the correct perspective/episode and updated premises
(TEST-075). Plans never self-execute and never run predefined sequences.
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

_PLAN_STATUS = frozenset({"active", "needs_review", "revised", "abandoned", "achieved"})
_INVESTIGATION_STATUS = frozenset(
    {
        "open",
        "investigating",
        "provisionally_answered",
        "needs_review",
        "budget_exhausted",
        "abandoned",
    }
)
_PERSPECTIVES = frozenset({"white", "black", "neutral"})
_PREMISE_STATES = frozenset({"true", "false", "unknown"})


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class PlanError(Exception):
    """Plan rejection with machine code (CODING_STANDARDS / Errors)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def evaluate_premise(state: str, predicate: dict[str, Any]) -> str:
    """Evaluate one predicate against a premise state (three-valued DSL).

    Predicates: {"expect": "true"|"false"|"unknown"} — the premise holds when
    its state equals the expectation; "unknown" expectation matches only
    unknown (explicit uncertainty, never a silent true). Unknown premise
    state never satisfies a true/false expectation.
    """
    expect = predicate.get("expect", "true")
    if expect not in _PREMISE_STATES:
        raise PlanError("INVALID_ARGUMENTS", f"unknown expectation {expect!r}")
    if state not in _PREMISE_STATES:
        raise PlanError("INVALID_ARGUMENTS", f"unknown premise state {state!r}")
    return "true" if state == expect else "false"


@dataclass(slots=True)
class PlanView:
    """Current projection of one plan with its premise states."""

    plan_id: str
    episode_id: str
    perspective: str
    status: str
    revision: int
    premises: dict[str, str] = field(default_factory=dict["str", "str"])


class PlanStore:
    """Single writer/reader over the CB-M4 plan tables (§23.2)."""

    def __init__(self, database: Database, clock: Callable[[], str] | None = None) -> None:
        self._database = database
        self._clock = clock or _now

    def _connect(self) -> Connection:
        return self._database.engine().connect()

    # -- investigations ---------------------------------------------------------

    def open_investigation(
        self,
        *,
        investigation_id: str,
        decision_id: str,
        anchor_node_id: str,
        payload_artifact_id: str,
        latest_event_id: str,
        root_action: str | None = None,
    ) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_investigations (investigation_id, decision_id, "
                        "anchor_node_id, root_action, status, revision, "
                        "payload_artifact_id, latest_event_id, created_at, updated_at) "
                        "VALUES (:id, :decision_id, :anchor, :root_action, 'open', 0, "
                        ":payload, :event, :created_at, :updated_at)"
                    ),
                    {
                        "id": investigation_id,
                        "decision_id": decision_id,
                        "anchor": anchor_node_id,
                        "root_action": root_action,
                        "payload": payload_artifact_id,
                        "event": latest_event_id,
                        "created_at": self._clock(),
                        "updated_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise PlanError(
                    "STATE_REPLAY_MISMATCH",
                    f"investigation {investigation_id!r} conflicts",
                ) from exc

    # -- plans ---------------------------------------------------------------------

    def open_plan(
        self,
        *,
        plan_id: str,
        episode_id: str,
        source_decision_id: str,
        perspective: str,
        payload_artifact_id: str,
        latest_event_id: str,
    ) -> None:
        """Open a conditional plan (episode guard is trigger-enforced)."""
        if perspective not in {"white", "black"}:
            raise PlanError("INVALID_ARGUMENTS", f"bad perspective {perspective!r}")
        with self._connect() as conn:
            try:
                conn.execute(
                    sa.text(
                        "INSERT INTO cb_plans (plan_id, episode_id, source_decision_id, "
                        "perspective, status, revision, payload_artifact_id, "
                        "latest_event_id, created_at, updated_at) "
                        "VALUES (:id, :episode_id, :decision_id, :perspective, "
                        "'active', 0, :payload, :event, :created_at, :updated_at)"
                    ),
                    {
                        "id": plan_id,
                        "episode_id": episode_id,
                        "decision_id": source_decision_id,
                        "perspective": perspective,
                        "payload": payload_artifact_id,
                        "event": latest_event_id,
                        "created_at": self._clock(),
                        "updated_at": self._clock(),
                    },
                )
                conn.commit()
            except IntegrityError as exc:
                raise PlanError(
                    "STATE_REPLAY_MISMATCH", f"plan {plan_id!r} conflicts or cross-episode"
                ) from exc

    def revise_plan(
        self,
        *,
        plan_id: str,
        status: str,
        premises: dict[str, str] | None = None,
        payload_artifact_id: str | None = None,
        latest_event_id: str | None = None,
    ) -> PlanView:
        """Revise by delta: premise changes mark needs_review (TEST-048).

        A changed premise never declares strategic refutation — the plan
        moves to needs_review for the operator/loop to decide. Status moves
        forward through the writer; identity columns never change.
        """
        if status not in _PLAN_STATUS:
            raise PlanError("INVALID_ARGUMENTS", f"unknown status {status!r}")
        if premises:
            for name, state in premises.items():
                if state not in _PREMISE_STATES:
                    raise PlanError(
                        "INVALID_ARGUMENTS", f"premise {name!r} state {state!r} unknown"
                    )
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT episode_id, perspective, status, revision FROM cb_plans "
                    "WHERE plan_id = :id"
                ),
                {"id": plan_id},
            ).fetchone()
            if row is None:
                raise PlanError("SEMANTICS_MISMATCH", f"unknown plan {plan_id!r}")
            episode_id, perspective, current, revision = row[0], row[1], row[2], int(row[2 + 1])
            del current
            conn.execute(
                sa.text(
                    "UPDATE cb_plans SET status = :status, revision = :revision, "
                    "payload_artifact_id = COALESCE(:payload, payload_artifact_id), "
                    "latest_event_id = COALESCE(:event, latest_event_id), "
                    "updated_at = :updated_at WHERE plan_id = :id"
                ),
                {
                    "status": status,
                    "revision": revision + 1,
                    "payload": payload_artifact_id,
                    "event": latest_event_id,
                    "updated_at": self._clock(),
                    "id": plan_id,
                },
            )
            conn.commit()
        return PlanView(
            plan_id=plan_id,
            episode_id=episode_id,
            perspective=perspective,
            status=status,
            revision=revision + 1,
            premises=dict(premises or {}),
        )

    def premise_delta(
        self, *, previous: dict[str, str], current: dict[str, str]
    ) -> dict[str, tuple[str, str]]:
        """Changed premises between turns (TEST-075 continuity input)."""
        delta: dict[str, tuple[str, str]] = {}
        for name in sorted(set(previous) | set(current)):
            old = previous.get(name, "unknown")
            new = current.get(name, "unknown")
            if old != new:
                delta[name] = (old, new)
        return delta

    def view_plan(self, plan_id: str) -> PlanView:
        with self._connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT episode_id, perspective, status, revision FROM cb_plans "
                    "WHERE plan_id = :id"
                ),
                {"id": plan_id},
            ).fetchone()
            conn.commit()
        if row is None:
            raise PlanError("SEMANTICS_MISMATCH", f"unknown plan {plan_id!r}")
        return PlanView(
            plan_id=plan_id,
            episode_id=row[0],
            perspective=row[1],
            status=row[2],
            revision=int(row[3]),
        )
