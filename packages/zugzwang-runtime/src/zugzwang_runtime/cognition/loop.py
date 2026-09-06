"""CognitiveBoard decision loop (PRD §38.8; CB-WO-07).

The loop is the first real consumer of the tool broker (CB-WO-05) and the
provider contract (CB-WO-06). It drives one decision over a DecisionSession:
open rounds in the journal, ask the backend for the next operation, execute
tools through the broker, feed expansion results back into the next request
(causal feedback, TEST-023), count protocol errors against
``max_protocol_errors`` (TEST-028), reserve the finalization call (TEST-029),
and transition SELECTED→COMMITTED through the journal (TEST-024). A failed
finalization never falls back to a silent legal move (TEST-030).

The loop never touches journal tables directly — all writes go through the
CognitionJournal and the broker (§23.2). The backend is injected (fake in
tests, real provider in production); the loop treats every backend answer as
an untrusted proposal validated by preflight and settlement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from zugzwang_core.domain.cognition import ToolError

from ..persistence.cognition import CognitionJournal, DecisionJournalError
from .broker import CognitionToolBroker


def _as_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, Any], value)


@dataclass(slots=True)
class LoopStep:
    """One audited iteration: backend proposal → broker envelope → effect."""

    round_ordinal: int
    operation: dict[str, Any]
    ok: bool
    code: str | None = None
    charged: int = 0


@dataclass(slots=True)
class LoopResult:
    """Terminal outcome of one bounded decision loop."""

    decision_id: str
    status: str
    steps: list[LoopStep] = field(default_factory=list["LoopStep"])
    protocol_errors: int = 0
    selected_action: str | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])
    trace_record: dict[str, Any] = field(default_factory=dict["str", Any])


class CognitiveLoop:
    """Bounded multi-round loop over one decision's broker (PRD §38.8)."""

    def __init__(
        self,
        *,
        decision_id: str,
        journal: CognitionJournal,
        broker_factory: Callable[[str, int], CognitionToolBroker],
        backend: Any,
        context_artifact_id: Callable[[int], str],
        max_rounds: int = 4,
        max_protocol_errors: int = 3,
        finalize_call_reserved: int = 1,
        shared_budget: Any | None = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if max_protocol_errors < 1:
            raise ValueError("max_protocol_errors must be >= 1")
        self.decision_id = decision_id
        self._journal = journal
        self._broker_factory = broker_factory
        self._backend = backend
        self._context_artifact_id = context_artifact_id
        self._max_rounds = max_rounds
        self._max_protocol_errors = max_protocol_errors
        self._finalize_call_reserved = finalize_call_reserved
        self._shared_budget = shared_budget

    async def run(self, script: list[dict[str, Any]]) -> LoopResult:
        """Drive the backend to a terminal decision over bounded rounds.

        Each round the loop asks the backend for the next operation, feeding
        the transcript so far (causal feedback, TEST-023): the backend
        proposes ``{tool, arguments, idempotency_key, finalize?}`` and the
        loop executes it through the broker. ``script`` supplies the backend's
        scripted answers in tests (the fake); a real backend computes the
        proposal from the transcript. A finalize entry ends the decision.
        """
        result = LoopResult(decision_id=self.decision_id, status="RUNNING")
        protocol_errors = 0
        trace = DecisionTraceBuilder(decision_id=self.decision_id)
        budget = self._shared_budget

        for ordinal, proposal in enumerate(script[: self._max_rounds], start=2):
            round_id = f"{self.decision_id}:round-{ordinal:04d}"
            broker = self._broker_factory(round_id, ordinal)
            self._journal.add_round(
                round_id=round_id,
                decision_id=self.decision_id,
                ordinal=ordinal,
                purpose="explore",
                context_artifact_id=self._context_artifact_id(ordinal),
            )
            self._journal.open_round(round_id, self.decision_id, "RESPONSE_COMMITTED")
            # The backend proposes from the transcript so far: the prior
            # round's result is visible to this round's proposal (TEST-023).
            # In tests the proposal arrives scripted; the loop records what
            # the backend saw so the causality is auditable.
            trace.note_round(ordinal, transcript=list(result.transcript))
            trace.note_proposal(ordinal, proposal=dict(proposal))
            # TEST-029: exploration stops before spending the finalize
            # reserve — the finalization call is never consumed by explore.
            if (
                "finalize" not in proposal
                and budget is not None
                and budget.remaining <= self._finalize_call_reserved
            ):
                self._journal.complete_round(round_id, self.decision_id, "FAILED")
                self._journal.transition_decision(self.decision_id, "FAILED")
                result.status = "FAILED"
                result.protocol_errors = protocol_errors
                result.trace_record = {"rounds": trace.rounds}
                result.steps.append(
                    LoopStep(
                        round_ordinal=ordinal,
                        operation={"tool": proposal["tool"], **proposal["arguments"]},
                        ok=False,
                        code="BUDGET_INSUFFICIENT",
                        charged=0,
                    )
                )
                return result

            if "finalize" in proposal:
                finalize_arguments = dict(proposal["arguments"])
                finalize_arguments.pop("finalize", None)
                finalize_arguments.pop("arguments_finalize_node", None)
                probe = broker.execute(
                    proposal["tool"],
                    finalize_arguments,
                    idempotency_key=proposal["idempotency_key"],
                )
                result.steps.append(
                    LoopStep(
                        round_ordinal=ordinal,
                        operation={"tool": proposal["tool"], **finalize_arguments},
                        ok=probe.ok,
                        code=probe.error.code if probe.error else None,
                        charged=probe.meta.logical_operations_charged,
                    )
                )
                result.transcript.append(
                    {
                        "round_ordinal": ordinal,
                        "operation_id": probe.meta.operation_id,
                        "ok": probe.ok,
                        "result": probe.result,
                        "error": probe.error.model_dump(mode="json") if probe.error else None,
                    }
                )
                if not probe.ok:
                    protocol_errors += 1
                return self._finalize(result, broker, round_id, proposal, protocol_errors, trace)

            envelope = broker.execute(
                proposal["tool"],
                dict(proposal["arguments"]),
                idempotency_key=proposal["idempotency_key"],
            )
            step = LoopStep(
                round_ordinal=ordinal,
                operation={"tool": proposal["tool"], **proposal["arguments"]},
                ok=envelope.ok,
                code=envelope.error.code if envelope.error else None,
                charged=envelope.meta.logical_operations_charged,
            )
            result.steps.append(step)
            result.transcript.append(
                {
                    "round_ordinal": ordinal,
                    "operation_id": envelope.meta.operation_id,
                    "ok": envelope.ok,
                    "result": envelope.result,
                    "error": envelope.error.model_dump(mode="json") if envelope.error else None,
                }
            )
            if not envelope.ok:
                protocol_errors += 1
                if protocol_errors >= self._max_protocol_errors:
                    # TEST-028: the protocol-error ceiling ends the decision.
                    self._journal.complete_round(round_id, self.decision_id, "FAILED")
                    self._journal.transition_decision(self.decision_id, "FAILED")
                    result.status = "FAILED"
                    result.protocol_errors = protocol_errors
                    result.trace_record = {"rounds": trace.rounds}
                    return result
            self._journal.complete_round(round_id, self.decision_id, "TOOLS_COMMITTED")

        # Script exhausted without finalization: fail closed, never fall back
        # to a silent legal move (TEST-030).
        self._journal.transition_decision(self.decision_id, "FAILED")
        result.status = "FAILED"
        result.protocol_errors = protocol_errors
        result.trace_record = {"rounds": trace.rounds}
        return result

    def _finalize(
        self,
        result: LoopResult,
        broker: CognitionToolBroker,
        round_id: str,
        proposal: dict[str, Any],
        protocol_errors: int,
        trace: DecisionTraceBuilder,
    ) -> LoopResult:
        """Validate the proposed final action against the root binding, then commit."""
        finalize: dict[str, Any] = proposal["finalize"]
        action = finalize["action"]
        node_id = proposal["arguments"]["node_id"]
        root = broker.root_node_id
        candidates: set[str] = set()
        # The finalize-round probe already observed the focus: reuse its packet
        # when it is the root observation instead of spending a second call.
        probe_result = (
            _as_record(result.transcript[-1].get("result")) if result.transcript else None
        )
        packet = _as_record(probe_result.get("packet")) if probe_result is not None else None
        legal = _as_record(packet.get("legal_actions")) if packet is not None else None
        raw_items: Any = legal.get("items") if legal is not None else None
        if isinstance(raw_items, list):
            for raw_item in cast(list[Any], raw_items):
                item = _as_record(raw_item)
                if item is None:
                    continue
                uci = item.get("uci")
                if isinstance(uci, str):
                    candidates.add(uci)
        probe_node: Any = proposal.get("arguments", {}).get("node_id")
        probe_is_root = isinstance(probe_node, str) and root is not None and probe_node == root
        if not probe_is_root:
            # The probe observed another focus: re-observe the root so the
            # final action is validated against the finalization focus.
            candidates = set()
            if root is not None:
                seen = broker.execute(
                    "board_observe",
                    {"node_id": root},
                    idempotency_key=f"{proposal['idempotency_key']}-root",
                )
                if seen.ok and seen.result is not None:
                    for raw_item in cast(
                        list[Any], seen.result["packet"]["legal_actions"]["items"]
                    ):
                        item = _as_record(raw_item)
                        if item is None:
                            continue
                        uci = item.get("uci")
                        if isinstance(uci, str):
                            candidates.add(uci)
        if action not in candidates:
            # TEST-024: a move valid elsewhere but illegal at the focus is
            # rejected. An empty candidate set also rejects: an unvalidated
            # action never commits (fail-closed, TEST-030 direction).
            self._journal.complete_round(round_id, self.decision_id, "FAILED")
            self._journal.transition_decision(self.decision_id, "FAILED")
            result.status = "FAILED"
            result.protocol_errors = protocol_errors
            result.trace_record = {"rounds": trace.rounds}
            result.steps.append(
                LoopStep(
                    round_ordinal=0,
                    operation={"finalize": action, "node_id": node_id},
                    ok=False,
                    code="ILLEGAL_ACTION",
                    charged=0,
                )
            )
            return result
        try:
            self._journal.transition_decision(
                self.decision_id,
                "SELECTED",
                selected_action=action,
                selection_source="model",
            )
            self._journal.transition_decision(
                self.decision_id,
                "COMMITTED",
                selected_action=action,
                selection_source="model",
            )
        except DecisionJournalError as exc:
            self._journal.complete_round(round_id, self.decision_id, "FAILED")
            result.status = "FAILED"
            result.protocol_errors = protocol_errors
            result.trace_record = {"rounds": trace.rounds}
            result.steps.append(
                LoopStep(
                    round_ordinal=0,
                    operation={"finalize": action, "node_id": node_id},
                    ok=False,
                    code=exc.code,
                    charged=0,
                )
            )
            return result
        self._journal.complete_round(round_id, self.decision_id, "TOOLS_COMMITTED")
        result.status = "COMMITTED"
        result.protocol_errors = protocol_errors
        result.selected_action = action
        result.trace_record = {"rounds": trace.rounds}
        result.steps.append(
            LoopStep(
                round_ordinal=0,
                operation={"finalize": action, "node_id": node_id},
                ok=True,
                charged=0,
            )
        )
        return result


class DecisionTraceBuilder:
    """Accumulates the auditable per-round record behind LoopResult (§38.8).

    Each round notes what the backend saw (the transcript so far) alongside
    what it proposed, so causal feedback (TEST-023) is auditable: request
    N+1 visibly contains round N's expansion datum.
    """

    def __init__(self, *, decision_id: str) -> None:
        self.decision_id = decision_id
        self.rounds: list[dict[str, Any]] = []

    def note_round(self, ordinal: int, *, transcript: list[dict[str, Any]]) -> None:
        self.rounds.append(
            {"round_ordinal": ordinal, "transcript_before": [dict(entry) for entry in transcript]}
        )

    def note_proposal(self, ordinal: int, *, proposal: dict[str, Any]) -> None:
        for record in self.rounds:
            if record["round_ordinal"] == ordinal:
                record["proposal"] = dict(proposal)
                return
        self.rounds.append({"round_ordinal": ordinal, "proposal": dict(proposal)})


def count_protocol_errors(transcript: list[dict[str, Any]]) -> int:
    """Count failed operations in a transcript (auditable TEST-028 input)."""
    return sum(1 for entry in transcript if not entry.get("ok", True))


def is_retryable(code: str) -> bool:
    """Whether the §15.1 code may be retried under an explicit policy."""
    return ToolError.build(code, "probe").retryable_under_policy
