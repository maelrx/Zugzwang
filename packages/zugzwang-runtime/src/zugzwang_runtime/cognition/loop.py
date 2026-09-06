"""CognitiveBoard decision loop (PRD §12, §38.8; CB-WO-07 + ZGW-0101).

The loop is the productive consumer of the tool broker (CB-WO-05) and the
provider contract (CB-WO-06). It drives one decision over a DecisionSession:
per round it builds a canonical ``ModelRequest`` whose transcript carries the
REAL prior tool results (causal feedback, TEST-023), calls the typed
``ModelBackend`` through its canonical ``infer`` interface, validates the
proposals that come back, executes them through the broker, feeds the
effective results into the next request, counts protocol errors against
``max_protocol_errors`` (TEST-028), reserves the finalization call in the
MODEL-calls budget (TEST-029), and transitions SELECTED→COMMITTED through the
journal (TEST-024). A failed finalization never falls back to a silent legal
move (TEST-030); the scripted behavior belongs to fake backends, never to
this loop.

The loop never touches journal tables directly — all writes go through the
CognitionJournal and the broker (§23.2). The backend is injected (fake in
tests, real provider adapter in production); the loop treats every backend
answer as an untrusted proposal validated by preflight and settlement.
Trace, usage, cost, route and tool_call ids come from the effective
execution; an unavailable datum stays unknown (never an invented zero).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from zugzwang_core.domain.cognition import ToolError
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    TextPart,
    ToolCallPart,
    ToolDefinition,
    ToolResultPart,
)

from ..persistence.cognition import CognitionJournal, DecisionJournalError
from .broker import CognitionToolBroker, ToolOperationBudget

FINALIZE_TOOL = "board_finalize"

BOARD_TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="board_observe",
        description="View the authorized L0 packet of one node (paginated legal set).",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "cursor": {"type": "integer", "minimum": 0},
            },
            "required": ["node_id"],
        },
    ),
    ToolDefinition(
        name="board_inspect",
        description="Inspect terminal/relations facts of one node without advancing.",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "query": {"type": "string", "enum": ["terminal", "relations", "complete"]},
            },
            "required": ["node_id"],
        },
    ),
    ToolDefinition(
        name="board_expand",
        description="Transition one node through legal actions; returns child nodes.",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "action_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
            },
            "required": ["node_id", "action_ids"],
        },
    ),
    ToolDefinition(
        name="board_compare",
        description="Formal differences between two nodes of this decision.",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "other_node_id": {"type": "string"},
            },
            "required": ["node_id", "other_node_id"],
        },
    ),
)


@dataclass(slots=True)
class LoopStep:
    """One audited iteration: backend proposal → broker envelope → effect."""

    round_ordinal: int
    operation: dict[str, Any]
    ok: bool
    code: str | None = None
    charged: int = 0


@dataclass(slots=True)
class ModelCallRecord:
    """One REAL inference call of the loop (no synthetic response_ok)."""

    round_ordinal: int
    attempt_id: str
    request_fingerprint: str
    response_ok: bool
    model: str
    usage: Any = None
    cost: Any = None
    latency_ms: int | None = None
    failure_code: str | None = None
    request_artifact_id: str | None = None
    response_artifact_id: str | None = None
    wire_route: str | None = None
    tool_call_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class LoopResult:
    """Terminal outcome of one bounded decision loop."""

    decision_id: str
    status: str
    steps: list[LoopStep] = field(default_factory=list["LoopStep"])
    calls: list[ModelCallRecord] = field(default_factory=list["ModelCallRecord"])
    protocol_errors: int = 0
    selected_action: str | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])
    trace_record: dict[str, Any] = field(default_factory=dict["str", Any])


class CognitiveLoop:
    """Bounded multi-round loop over one decision's broker (PRD §12/§38.8).

    ``backend`` is the typed ModelBackend port: every round the loop builds a
    canonical ModelRequest from the transcript so far and calls ``infer``.
    Proposals are validated then executed through the broker; the effective
    envelope becomes part of the next request (TEST-023). ``finalize``
    proposals commit only when the action resolves against the REAL root
    (TEST-024); early finalization simply stops the loop (TEST-025).
    """

    def __init__(
        self,
        *,
        decision_id: str,
        journal: CognitionJournal,
        broker_factory: Callable[[str, int], CognitionToolBroker],
        backend: Any,
        context_artifact_id: Callable[[int, ModelRequest], str],
        model: ModelRef | None = None,
        max_rounds: int = 4,
        max_protocol_errors: int = 3,
        finalize_call_reserved: int = 1,
        interaction_mode: str = "native_tools",
        shared_budget: ToolOperationBudget | None = None,
        call_context: CallContext | None = None,
        system_prompt: str | None = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if max_protocol_errors < 1:
            raise ValueError("max_protocol_errors must be >= 1")
        if finalize_call_reserved < 0:
            raise ValueError("finalize_call_reserved must be >= 0")
        if interaction_mode not in {"native_tools", "json_commands"}:
            raise ValueError("interaction_mode must be native_tools or json_commands")
        self.decision_id = decision_id
        self._journal = journal
        self._broker_factory = broker_factory
        self._backend = backend
        self._context_artifact_id = context_artifact_id
        self._model = model or ModelRef(backend="fake", provider="fake", model="scripted")
        self._max_rounds = max_rounds
        self._max_protocol_errors = max_protocol_errors
        self._finalize_call_reserved = finalize_call_reserved
        self._interaction_mode = interaction_mode
        self._shared_budget = shared_budget
        self._call_context = call_context

    # -- productive entry point -------------------------------------------------

    async def run(self) -> LoopResult:
        """Drive the typed backend to a terminal decision over bounded rounds."""
        result = LoopResult(decision_id=self.decision_id, status="RUNNING")
        protocol_errors = 0
        trace = DecisionTraceBuilder(decision_id=self.decision_id)

        # Round 0001 is the decision opening record (session.open); the loop
        # drives bounded rounds starting at ordinal 2 (§12.2).
        first_ordinal = 2
        last_ordinal = self._max_rounds + 1
        for ordinal in range(first_ordinal, last_ordinal + 1):
            round_id = f"{self.decision_id}:round-{ordinal:04d}"
            broker = self._broker_for_round(round_id, ordinal)

            # TEST-029: the finalize reserve is MODEL calls, never board
            # operations. When only the reserve remains, the round runs with
            # purpose=finalize: a finalize proposal commits, but exploration
            # is refused without execution.
            rounds_left = last_ordinal - ordinal + 1
            reserving = rounds_left <= self._finalize_call_reserved
            round_purpose = "finalize" if reserving else "explore"

            proposal_round = _RoundPlan(round_id=round_id, ordinal=ordinal)
            request = self._build_request(ordinal, list(result.transcript))
            request_artifact_id = self._context_artifact_id(ordinal, request)
            if not self._journal.round_exists(round_id):
                # One journal round per bounded iteration (§12.2); its
                # context is the exact request artifact (FR-020).
                self._journal.add_round(
                    round_id=round_id,
                    decision_id=self.decision_id,
                    ordinal=ordinal,
                    purpose=round_purpose,
                    context_artifact_id=request_artifact_id,
                )
            self._journal.open_round(round_id, self.decision_id, "RESPONSE_COMMITTED")
            trace.note_round(
                ordinal,
                request_fingerprint=request_fingerprint(request),
                transcript=[dict(entry) for entry in result.transcript],
            )

            try:
                response = await self._backend.infer(request, self._call_context_for(ordinal))
            except Exception as exc:
                self._record_call(
                    result,
                    proposal_round,
                    request,
                    ok=False,
                    failure_code=type(exc).__name__,
                    ordinal=ordinal,
                    request_artifact_id=request_artifact_id,
                )
                protocol_errors += 1
                self._journal.complete_round(round_id, self.decision_id, "FAILED")
                if protocol_errors >= self._max_protocol_errors:
                    return self._fail_closed(
                        result, round_id, protocol_errors, trace, code="PROTOCOL_ERROR"
                    )
                result.protocol_errors = protocol_errors
                continue

            normalized = response.response
            self._record_call(
                result,
                proposal_round,
                request,
                ok=True,
                response=normalized,
                ordinal=ordinal,
                request_artifact_id=request_artifact_id,
            )

            proposals = self._parse_proposals(normalized, ordinal)
            trace.note_proposal(ordinal, proposals=proposals)

            finalize_proposal = next((p for p in proposals if p.tool == FINALIZE_TOOL), None)
            if reserving and finalize_proposal is None:
                # The reserved call is never spent exploring (TEST-029).
                self._journal.complete_round(round_id, self.decision_id, "FAILED")
                return self._fail_closed(
                    result,
                    round_id,
                    protocol_errors,
                    trace,
                    code="BUDGET_INSUFFICIENT",
                    note="finalize reserve reached; exploration must not consume it",
                )
            if finalize_proposal is not None:
                for proposal in proposals:
                    if proposal is finalize_proposal:
                        break
                    self._execute(result, broker, proposal, ordinal)
                return self._finalize(
                    result,
                    broker,
                    round_id,
                    finalize_proposal,
                    protocol_errors,
                    trace,
                    ordinal=ordinal,
                )

            for proposal in proposals:
                step = self._execute(result, broker, proposal, ordinal)
                if not step.ok:
                    protocol_errors += 1
            if protocol_errors >= self._max_protocol_errors:
                # TEST-028: the protocol-error ceiling ends the decision.
                self._journal.complete_round(round_id, self.decision_id, "FAILED")
                return self._fail_closed(result, round_id, protocol_errors, trace)
            self._journal.complete_round(round_id, self.decision_id, "TOOLS_COMMITTED")

        # Round budget exhausted without finalization: fail closed, never fall
        # back to a silent legal move (TEST-030).
        return self._fail_closed(
            result,
            f"{self.decision_id}:round-{last_ordinal:04d}",
            protocol_errors,
            trace,
        )

    # -- wiring ------------------------------------------------------------------

    def _broker_for_round(self, round_id: str, ordinal: int) -> CognitionToolBroker:
        return self._broker_factory(round_id, ordinal)

    def _call_context_for(self, ordinal: int) -> CallContext:
        if self._call_context is not None:
            return self._call_context
        return CallContext(
            run_id=self.decision_id,
            step_id=f"{self.decision_id}:round-{ordinal:04d}",
            attempt_id=f"{self.decision_id}:{ordinal:04d}",
        )

    # -- request building (§12.4: what the model receives) -----------------------

    def _build_request(self, ordinal: int, transcript: list[dict[str, Any]]) -> ModelRequest:
        messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                parts=(TextPart(text=self._default_system_prompt()),),
            )
        ]
        for entry in transcript:
            tool_call_id = _entry_str(entry, "tool_call_id")
            tool_name = _entry_str(entry, "tool")
            raw_arguments: Any = entry.get("arguments") if "arguments" in entry else {}
            arguments: dict[str, Any] = (
                cast(dict[str, Any], raw_arguments) if isinstance(raw_arguments, dict) else {}
            )
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=(
                        ToolCallPart(
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            arguments=arguments,
                        ),
                    ),
                )
            )
            content = entry.get("result") if entry.get("ok") else entry.get("error")
            text_content: str = (
                content.decode("utf-8")
                if isinstance(content, bytes)
                else json.dumps(content, sort_keys=True, separators=(",", ":"))
            )
            messages.append(
                Message(
                    role=MessageRole.TOOL,
                    parts=(
                        ToolResultPart(
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            content=text_content,
                            is_error=not bool(entry.get("ok")),
                        ),
                    ),
                )
            )
        return ModelRequest(
            model=self._model,
            messages=tuple(messages),
            tools=BOARD_TOOL_DEFINITIONS if self._interaction_mode == "native_tools" else (),
            metadata={
                "decision_id": self.decision_id,
                "round_ordinal": ordinal,
                "interaction_mode": self._interaction_mode,
            },
        )

    def _default_system_prompt(self) -> str:
        if self._interaction_mode == "native_tools":
            return (
                "You are navigating one decision's hypothetical search graph. "
                "Use the board tools to observe the root, expand legal actions "
                f"(action ids come from observations), and when ready call "
                f"{FINALIZE_TOOL} with the ROOT node and the chosen action_id."
            )
        return (
            "You are navigating one decision's hypothetical search graph. "
            'Reply with ONE JSON command: {"command": <tool>, "arguments": {...}}. '
            f'To finish, use {{"command": "{FINALIZE_TOOL}", '
            '"arguments": {"node_id": <root>, "action_id": <id>}}}.'
        )

    # -- response parsing (native tools vs JSON commands, §12.1) ------------------

    def _parse_proposals(self, response: NormalizedResponse, ordinal: int) -> list[_Proposal]:
        proposals: list[_Proposal] = []
        for index, call in enumerate(response.tool_calls):
            tool = call.tool_name
            synthetic_id = f"{self.decision_id}:r{ordinal:04d}:native:{index}"
            proposals.append(
                _Proposal(
                    provider_tool_call_id=call.tool_call_id or synthetic_id,
                    tool=tool,
                    arguments=dict(call.arguments),
                )
            )
        if not proposals:
            text = response.text().strip()
            if text:
                command = _parse_json_command(text)
                if command is not None:
                    synthetic_id = f"{self.decision_id}:r{ordinal:04d}:json:0"
                    proposals.append(
                        _Proposal(
                            provider_tool_call_id=synthetic_id,
                            tool=str(command.get("command", "")),
                            arguments=cast(dict[str, Any], command.get("arguments") or {}),
                        )
                    )
        return proposals

    # -- execution ----------------------------------------------------------------

    def _execute(
        self,
        result: LoopResult,
        broker: CognitionToolBroker,
        proposal: _Proposal,
        ordinal: int,
    ) -> LoopStep:
        idempotency_key = f"{self.decision_id}:{proposal.provider_tool_call_id}"
        envelope = broker.execute(
            proposal.tool,
            dict(proposal.arguments),
            idempotency_key=idempotency_key,
            provider_tool_call_id=proposal.provider_tool_call_id,
        )
        step = LoopStep(
            round_ordinal=ordinal,
            operation={"tool": proposal.tool, **proposal.arguments},
            ok=envelope.ok,
            code=envelope.error.code if envelope.error else None,
            charged=envelope.meta.logical_operations_charged,
        )
        result.steps.append(step)
        result.transcript.append(
            {
                "round_ordinal": ordinal,
                "tool_call_id": proposal.provider_tool_call_id,
                "operation_id": envelope.meta.operation_id,
                "tool": proposal.tool,
                "arguments": dict(proposal.arguments),
                "ok": envelope.ok,
                "result": envelope.result,
                "error": envelope.error.model_dump(mode="json") if envelope.error else None,
            }
        )
        return step

    # -- finalization (TEST-024/025; FR-012) ---------------------------------------

    def _finalize(
        self,
        result: LoopResult,
        broker: CognitionToolBroker,
        round_id: str,
        proposal: _Proposal,
        protocol_errors: int,
        trace: DecisionTraceBuilder,
        *,
        ordinal: int,
    ) -> LoopResult:
        """Validate the proposed final action against the ROOT, then commit."""
        node_id = proposal.arguments.get("node_id")
        root = broker.root_node_id
        action_ref = proposal.arguments.get("action_id") or proposal.arguments.get("action")
        resolved = broker.resolve_action(
            node_id if isinstance(node_id, str) else (root or ""),
            action_ref if isinstance(action_ref, str) else "",
        )
        at_root = isinstance(node_id, str) and root is not None and node_id == root
        if resolved is None or not at_root:
            # TEST-024: a move valid elsewhere but illegal at the root is
            # rejected; an unresolvable proposal never commits (fail-closed).
            self._journal.complete_round(round_id, self.decision_id, "FAILED")
            self._journal.transition_decision(self.decision_id, "FAILED")
            result.status = "FAILED"
            result.protocol_errors = protocol_errors
            result.trace_record = {"rounds": trace.rounds}
            result.steps.append(
                LoopStep(
                    round_ordinal=ordinal,
                    operation={"finalize": action_ref, "node_id": node_id},
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
                selected_action=resolved,
                selection_source="model",
            )
            self._journal.transition_decision(
                self.decision_id,
                "COMMITTED",
                selected_action=resolved,
                selection_source="model",
            )
        except DecisionJournalError as exc:
            self._journal.complete_round(round_id, self.decision_id, "FAILED")
            result.status = "FAILED"
            result.protocol_errors = protocol_errors
            result.trace_record = {"rounds": trace.rounds}
            result.steps.append(
                LoopStep(
                    round_ordinal=ordinal,
                    operation={"finalize": action_ref, "node_id": node_id},
                    ok=False,
                    code=exc.code,
                    charged=0,
                )
            )
            return result
        self._journal.complete_round(round_id, self.decision_id, "TOOLS_COMMITTED")
        result.status = "COMMITTED"
        result.protocol_errors = protocol_errors
        result.selected_action = resolved
        result.trace_record = {"rounds": trace.rounds}
        result.steps.append(
            LoopStep(
                round_ordinal=ordinal,
                operation={"finalize": resolved, "node_id": node_id},
                ok=True,
                charged=0,
            )
        )
        return result

    # -- helpers ---------------------------------------------------------------------

    def _record_call(
        self,
        result: LoopResult,
        round_plan: _RoundPlan,
        request: ModelRequest,
        *,
        ok: bool,
        ordinal: int,
        request_artifact_id: str | None,
        response: NormalizedResponse | None = None,
        failure_code: str | None = None,
    ) -> None:
        usage = response.usage if response is not None else None
        cost = response.cost if response is not None else None
        latency: int | None = None
        started = response.started_at if response is not None else None
        finished = response.finished_at if response is not None else None
        if started is not None and finished is not None:
            latency = int((finished - started).total_seconds() * 1000)
        result.calls.append(
            ModelCallRecord(
                round_ordinal=ordinal,
                attempt_id=f"{self.decision_id}:{ordinal:04d}",
                request_fingerprint=request_fingerprint(request),
                response_ok=ok,
                model=str(self._model),
                usage=usage,
                cost=cost,
                latency_ms=latency,
                failure_code=failure_code,
                request_artifact_id=request_artifact_id,
                tool_call_ids=tuple(
                    call.tool_call_id for call in (response.tool_calls if response else ())
                ),
            )
        )

    def _fail_closed(
        self,
        result: LoopResult,
        round_id: str,
        protocol_errors: int,
        trace: DecisionTraceBuilder,
        *,
        code: str = "PROTOCOL_ERROR",
        note: str | None = None,
    ) -> LoopResult:
        with contextlib.suppress(DecisionJournalError):
            self._journal.transition_decision(self.decision_id, "FAILED")
        result.status = "FAILED"
        result.protocol_errors = protocol_errors
        record: dict[str, Any] = {"rounds": trace.rounds, "failure_code": code}
        if note:
            record["note"] = note
        result.trace_record = record
        return result


@dataclass(slots=True)
class _RoundPlan:
    round_id: str
    ordinal: int


@dataclass(slots=True)
class _Proposal:
    provider_tool_call_id: str
    tool: str
    arguments: dict[str, Any]


def _entry_str(entry: dict[str, Any], key: str) -> str:
    value: Any = entry.get(key, "")
    return value if isinstance(value, str) else ""


def _parse_json_command(text: str) -> dict[str, Any] | None:
    """Parse one JSON command (json_commands mode); malformed never executes."""
    try:
        value: Any = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
        except ValueError:
            return None
    return cast("dict[str, Any] | None", value if isinstance(value, dict) else None)


def request_fingerprint(request: ModelRequest) -> str:
    """Stable fingerprint of the exact request bytes (§22.1 auditability)."""
    return f"reqfp:v1:{hashlib.sha256(request.model_dump_json().encode('utf-8')).hexdigest()}"


def count_protocol_errors(transcript: list[dict[str, Any]]) -> int:
    """Count failed operations in a transcript (auditable TEST-028 input)."""
    return sum(1 for entry in transcript if not entry.get("ok", True))


def is_retryable(code: str) -> bool:
    """Whether the §15.1 code may be retried under an explicit policy."""
    return ToolError.build(code, "probe").retryable_under_policy


class DecisionTraceBuilder:
    """Accumulates the auditable per-round record behind LoopResult (§38.8).

    Each round notes the request fingerprint, what the backend saw (the
    transcript so far) alongside what it proposed, so causal feedback
    (TEST-023) is auditable: request N+1 visibly contains round N's
    expansion datum.
    """

    def __init__(self, *, decision_id: str) -> None:
        self.decision_id = decision_id
        self.rounds: list[dict[str, Any]] = []

    def note_round(
        self, ordinal: int, *, request_fingerprint: str, transcript: list[dict[str, Any]]
    ) -> None:
        self.rounds.append(
            {
                "round_ordinal": ordinal,
                "request_fingerprint": request_fingerprint,
                "transcript_before": [dict(entry) for entry in transcript],
            }
        )

    def note_proposal(self, ordinal: int, *, proposals: list[_Proposal]) -> None:
        for record in self.rounds:
            if record["round_ordinal"] == ordinal:
                record["proposals"] = [
                    {
                        "provider_tool_call_id": p.provider_tool_call_id,
                        "tool": p.tool,
                        "arguments": dict(p.arguments),
                    }
                    for p in proposals
                ]
                return
        self.rounds.append({"round_ordinal": ordinal, "proposals": []})
