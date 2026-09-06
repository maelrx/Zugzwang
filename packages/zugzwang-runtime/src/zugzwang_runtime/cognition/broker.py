"""CognitiveBoard tool broker (PRD §11, §38.6; CB-WO-05).

The broker is the single authorized door to the L0 tools: it validates the
tool name, node scope, request size and budget, executes through the
deterministic perception, settles the operation with its result artifact,
records the observation, and returns the normalized §42.6 envelope. No fast
path skips it (§38.6: "toda tool entra pelo executor").

Charge rules (§15.1/§21): an operation that is recorded (PREPARED) and then
settled charges its logical operations — one per expand item, one otherwise —
except a BUDGET_INSUFFICIENT rejection, which charges nothing. Failures that
happen before an operation row exists (unknown tool, oversized request,
journal conflict) charge nothing and create no observation: nothing was
exposed from any node's projection.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

from zugzwang_chess.cognition import ChessPerception
from zugzwang_core.domain.canonical import canonical_json_bytes, sha256_hex
from zugzwang_core.domain.cognition import (
    EnvelopeMeta,
    ToolEnvelope,
    ToolError,
    observation_id_v2,
    operation_id_v2,
)

from ..persistence.cognition import CognitionJournal, DecisionJournalError

TOOL_CATALOG = frozenset({"board_observe", "board_inspect", "board_expand", "board_compare"})

DEFAULT_MAX_BATCH = 16
DEFAULT_MAX_ARGUMENT_BYTES = 8192

# Codes that settle REJECTED (the request itself was refused); any other
# failure during execution settles FAILED (§12.2 round/tool statuses).
_REJECTED_CODES = frozenset(
    {"NODE_SCOPE_MISMATCH", "INVALID_ARGUMENTS", "BUDGET_INSUFFICIENT", "ACTION_STATE_MISMATCH"}
)

_TOOL_KIND = {
    "board_observe": "view",
    "board_inspect": "inspect",
    "board_expand": "expand",
    "board_compare": "compare",
}

ArtifactSink = Callable[[bytes, str], str]
ArtifactLoader = Callable[[str], "bytes | None"]


class ToolExecutionError(Exception):
    """Tool-internal failure carrying a §15.1 catalogue code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolOperationBudget:
    """Shared tool-operations pool of one decision (§21; TEST-031/032/036).

    One authority instance is passed to every broker of the decision (and, in
    later work orders, to the loop): changing focus or branching never creates
    a new pool. Wiring to the run-level budget ledger arrives with CB-WO-07;
    the invariant exercised here is the single shared pool itself.
    """

    def __init__(self, remaining: int) -> None:
        if remaining < 0:
            raise ValueError("remaining tool operations must be >= 0")
        self.remaining = remaining

    def allows(self, amount: int) -> bool:
        return 0 <= amount <= self.remaining

    def debit(self, amount: int) -> None:
        if amount < 0 or amount > self.remaining:
            raise ValueError(f"cannot debit {amount} tool operations; only {self.remaining} remain")
        self.remaining -= amount


class CognitionToolBroker:
    """Executes authorized L0 tools over one decision's journal + perception."""

    def __init__(
        self,
        *,
        decision_id: str,
        round_id: str,
        round_ordinal: int,
        journal: CognitionJournal,
        perception: ChessPerception,
        policy_hash: str,
        states: dict[str, Any],
        budget: ToolOperationBudget,
        artifact_sink: ArtifactSink,
        artifact_loader: ArtifactLoader,
        max_batch: int = DEFAULT_MAX_BATCH,
        max_argument_bytes: int = DEFAULT_MAX_ARGUMENT_BYTES,
    ) -> None:
        self.decision_id = decision_id
        self._round_id = round_id
        self._round_ordinal = round_ordinal
        self._journal = journal
        self._perception = perception
        self._policy_hash = policy_hash
        self._states = dict(states)
        self._budget = budget
        self._artifact_sink = artifact_sink
        self._artifact_loader = artifact_loader
        self._max_batch = max_batch
        self._max_argument_bytes = max_argument_bytes
        bound = self._journal.bound_node_ids(decision_id)
        self._root_node_id = bound[0] if bound else None
        self._exposure_sequence = self._journal.next_exposure_sequence(decision_id)
        self._call_count = 0

    # -- public ---------------------------------------------------------------

    def execute(
        self, tool: str, arguments: dict[str, Any], *, idempotency_key: str
    ) -> ToolEnvelope:
        """Run one tool through the full authorized path (§11.1, §38.6)."""
        self._call_count += 1
        operation_id = operation_id_v2(self.decision_id, self._round_ordinal, idempotency_key)

        if tool not in TOOL_CATALOG:
            return self._unrecorded_failure(
                idempotency_key,
                ToolError.build(
                    "TOOL_NOT_ALLOWED", f"tool {tool!r} is not in the authorized catalog"
                ),
            )

        raw = canonical_json_bytes(arguments)
        if len(raw) > self._max_argument_bytes:
            # TEST-020: refused before any allocation or persistence.
            return self._unrecorded_failure(
                idempotency_key,
                ToolError.build("INVALID_ARGUMENTS", "arguments exceed the request size limit"),
            )

        # Structural batch-count gate before persistence: an unbounded batch is
        # refused before CAS storage and journaling ("limites antes da reserva
        # e execução", §30.2). Semantic layers (budget, scope) stay in preflight.
        if tool == "board_expand":
            gate_batch: Any = arguments.get("action_ids", [])
            gate_items = cast(list[Any], gate_batch) if isinstance(gate_batch, list) else []
            if gate_items and len(gate_items) > self._max_batch:
                return self._unrecorded_failure(
                    idempotency_key,
                    ToolError.build(
                        "INVALID_ARGUMENTS",
                        f"action_ids exceeds the batch limit of {self._max_batch}",
                    ),
                )

        try:
            stored_operation_id, created = self._journal.record_tool_operation(
                operation_id=operation_id,
                decision_id=self.decision_id,
                round_id=self._round_id,
                provider_tool_call_id=f"{idempotency_key}:{self._call_count}",
                idempotency_key=idempotency_key,
                tool_name=tool,
                arguments_hash=hashlib.sha256(raw).hexdigest(),
                arguments_artifact_id=self._artifact_sink(raw, "application/json"),
            )
        except DecisionJournalError as exc:
            # Catalogue-derived flags only: ToolError.build validates the code
            # against §15.1 and derives retryable_under_policy (never hand-set).
            return self._unrecorded_failure(idempotency_key, ToolError.build(exc.code, str(exc)))

        if not created:
            return self._replay(stored_operation_id)

        error = self._preflight(tool, arguments)
        if error is not None:
            return self._settle_failure(stored_operation_id, tool, arguments, error)

        try:
            payload = self._execute_tool(tool, arguments)
        except ToolExecutionError as exc:
            return self._settle_failure(
                stored_operation_id, tool, arguments, ToolError.build(exc.code, exc.message)
            )
        except Exception as exc:
            return self._settle_failure(
                stored_operation_id,
                tool,
                arguments,
                ToolError.build("OUTPUT_CONTRACT_VIOLATION", f"tool failed internally: {exc}"),
            )

        result_bytes = canonical_json_bytes(payload)
        result_artifact_id = self._artifact_sink(result_bytes, "application/json")
        self._journal.settle_tool_operation(
            operation_id=stored_operation_id,
            decision_id=self.decision_id,
            status="COMMITTED",
            result_artifact_id=result_artifact_id,
            error_code=None,
        )
        return self._expose(
            stored_operation_id, tool, arguments, payload, result_artifact_id, result_bytes
        )

    # -- replay (TEST-034/035) ---------------------------------------------------

    def _replay(self, stored_operation_id: str) -> ToolEnvelope:
        """Same idempotency key: repeat the stored result, never the effect."""
        artifact_id = self._journal.result_artifact_id(stored_operation_id)
        if artifact_id is None:
            return self._unrecorded_failure(
                stored_operation_id,
                ToolError.build(
                    "PERSISTENCE_FAILED", "replayed operation has no settled result yet"
                ),
            )
        data = self._artifact_loader(artifact_id)
        if data is None:
            # CAS lost the object behind a registered reference: integrity
            # failure, never silently re-executed (TEST-034, §10.5).
            return self._unrecorded_failure(
                stored_operation_id,
                ToolError.build("PERSISTENCE_FAILED", "result artifact failed integrity check"),
            )
        try:
            payload = _decode_artifact(data)
        except ValueError:
            # A malformed stored payload is an integrity failure, never a crash:
            # fail closed without re-executing (§10.5, TEST-021).
            return self._unrecorded_failure(
                stored_operation_id,
                ToolError.build("PERSISTENCE_FAILED", "stored result failed contract check"),
            )
        semantic_hash = sha256_hex(data)
        raw_error: Any = payload.get("error")
        error_part = cast(dict[str, Any], raw_error) if isinstance(raw_error, dict) else None
        if error_part is not None:
            code = error_part.get("code")
            message = error_part.get("message")
            if not isinstance(code, str) or not isinstance(message, str):
                return self._unrecorded_failure(
                    stored_operation_id,
                    ToolError.build("PERSISTENCE_FAILED", "stored error failed contract check"),
                )
            return ToolEnvelope(
                ok=False,
                meta=self._meta(stored_operation_id, charged=0, semantic_hash=None),
                result=None,
                error=ToolError.build(code, message),
            )
        return ToolEnvelope(
            ok=True,
            meta=self._meta(stored_operation_id, charged=0, semantic_hash=semantic_hash),
            result=payload,
            error=None,
        )

    # -- preflight (§11.2 validation in layers) ---------------------------------

    def _preflight(self, tool: str, arguments: dict[str, Any]) -> ToolError | None:
        raw_node: Any = arguments.get("node_id")
        if not isinstance(raw_node, str) or not raw_node:
            # Absent or malformed is a client error, not a scope probe.
            return ToolError.build("INVALID_ARGUMENTS", "node_id must be a non-empty string")
        node_id = raw_node
        if node_id not in self._states:
            # TEST-019: foreign node denied before any projection is built.
            return ToolError.build("NODE_SCOPE_MISMATCH", "node is not bound to this decision")
        scope_error = self._check_scope(node_id)
        if scope_error is not None:
            return scope_error
        cost = 1
        if tool == "board_expand":
            raw_batch: Any = arguments.get("action_ids", [])
            if not isinstance(raw_batch, list) or not raw_batch:
                return ToolError.build("INVALID_ARGUMENTS", "action_ids must be a non-empty list")
            batch = cast(list[Any], raw_batch)
            if any(not isinstance(action_id, str) for action_id in batch):
                return ToolError.build("INVALID_ARGUMENTS", "action_ids must be strings")
            if len(batch) > self._max_batch:
                return ToolError.build(
                    "INVALID_ARGUMENTS",
                    f"action_ids exceeds the batch limit of {self._max_batch}",
                )
            cost = len(batch)
        if tool == "board_observe":
            raw_cursor: Any = arguments.get("cursor", 0)
            if isinstance(raw_cursor, bool) or not isinstance(raw_cursor, int) or raw_cursor < 0:
                return ToolError.build("INVALID_ARGUMENTS", "cursor must be an integer >= 0")
        if tool == "board_inspect":
            raw_query: Any = arguments.get("query", "terminal")
            if raw_query not in {"terminal", "relations", "complete"}:
                return ToolError.build(
                    "INVALID_ARGUMENTS",
                    "query must be one of terminal, relations, complete",
                )
        if tool == "board_compare":
            raw_other: Any = arguments.get("other_node_id")
            if not isinstance(raw_other, str) or not raw_other:
                return ToolError.build(
                    "INVALID_ARGUMENTS", "other_node_id must be a non-empty string"
                )
            if raw_other not in self._states:
                return ToolError.build(
                    "NODE_SCOPE_MISMATCH", "other node is not bound to this decision"
                )
        # Every recorded operation is budget-checked before it runs — a
        # ValueError from debit can never escape execute() (fail-closed).
        if not self._budget.allows(cost):
            return ToolError.build(
                "BUDGET_INSUFFICIENT",
                f"cost of {cost} exceeds the {self._budget.remaining} remaining tool operations",
            )
        return None

    @property
    def root_node_id(self) -> str | None:
        """First bound node of the decision (the loop's finalization focus)."""
        return self._root_node_id

    def _check_scope(self, node_id: str) -> ToolError | None:
        if node_id not in self._journal.bound_node_ids(self.decision_id):
            return ToolError.build("NODE_SCOPE_MISMATCH", "node is not bound to this decision")
        return None

    # -- tool implementations -----------------------------------------------------

    def _execute_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        node_id: str = arguments["node_id"]
        state: Any = self._states[node_id]
        if tool == "board_observe":
            packet = self._perception.build_packet(
                state, node_id, cursor=int(arguments.get("cursor", 0))
            )
            return {
                "packet": packet.model_dump(mode="json"),
                "content_hash": packet.content_hash(),
            }
        if tool == "board_inspect":
            packet = self._perception.build_packet(state, node_id)
            query = arguments.get("query", "terminal")
            facts: dict[str, Any] = {"terminal": packet.terminal.model_dump(mode="json")}
            if query in {"relations", "complete"}:
                facts["relations"] = [dict(item) for item in packet.relations.items]
            return {"facts": facts, "complete": True, "content_hash": packet.content_hash()}
        if tool == "board_expand":
            action_ids: Any = arguments["action_ids"]
            if not isinstance(action_ids, list) or not all(
                isinstance(item, str) for item in cast(list[Any], action_ids)
            ):
                raise ToolExecutionError("INVALID_ARGUMENTS", "action_ids must be strings")
            return self._expand(node_id, cast(list[str], action_ids))
        other_node_id = arguments["other_node_id"]
        if not isinstance(other_node_id, str):
            raise ToolExecutionError("INVALID_ARGUMENTS", "other_node_id must be a string")
        return self._compare(node_id, other_node_id)

    def _expand(self, node_id: str, action_ids: list[str]) -> dict[str, Any]:
        state: Any = self._states[node_id]
        packet = self._perception.build_packet(state, node_id)
        legal = {item.action_id: item.uci for item in packet.legal_actions.items}
        results: list[dict[str, Any]] = []
        for action_id in action_ids:
            if action_id not in legal:
                # TEST-006 at broker level: a foreign action never expands.
                raise ToolExecutionError(
                    "ACTION_STATE_MISMATCH", f"action {action_id!r} does not belong to this state"
                )
            results.append({"action_id": action_id, "uci": legal[action_id], "expanded": True})
        return {"results": results, "content_hash": packet.content_hash()}

    def _compare(self, node_id: str, other_node_id: str) -> dict[str, Any]:
        left = self._perception.build_packet(self._states[node_id], node_id)
        right = self._perception.build_packet(self._states[other_node_id], other_node_id)
        return {
            "formal_differences": {
                "same_content": left.content_hash() == right.content_hash(),
                "same_side": left.state.side_to_move == right.state.side_to_move,
            },
            "content_hash": right.content_hash(),
        }

    # -- exposure and envelopes ----------------------------------------------------

    def _expose(
        self,
        operation_id: str,
        tool: str,
        arguments: dict[str, Any],
        payload: dict[str, Any],
        result_artifact_id: str,
        result_bytes: bytes,
    ) -> ToolEnvelope:
        charged = self._charge(tool, arguments)
        self._exposure_sequence = self._journal.next_exposure_sequence(self.decision_id)
        semantic_hash = sha256_hex(result_bytes)
        self._journal.record_observation(
            observation_id=observation_id_v2(
                semantic_hash, self._round_ordinal, self._exposure_sequence
            ),
            decision_id=self.decision_id,
            node_id=arguments["node_id"],
            round_id=self._round_id,
            operation_id=operation_id,
            kind=_TOOL_KIND[tool],
            payload_artifact_id=result_artifact_id,
            semantic_hash=semantic_hash,
            policy_hash=self._policy_hash,
            exposure_sequence=self._exposure_sequence,
            available_before_selection=True,
        )
        return ToolEnvelope(
            ok=True,
            meta=self._meta(operation_id, charged=charged, semantic_hash=semantic_hash),
            result=payload,
            error=None,
        )

    def _charge(self, tool: str, arguments: dict[str, Any]) -> int:
        """Debit the shared pool; expand charges per item, others per call."""
        charged = len(arguments["action_ids"]) if tool == "board_expand" else 1
        self._budget.debit(charged)
        return charged

    def _settle_failure(
        self, operation_id: str, tool: str, arguments: dict[str, Any], error: ToolError
    ) -> ToolEnvelope:
        status = "REJECTED" if error.code in _REJECTED_CODES else "FAILED"
        # Scope probes and budget refusals never charge: authorization itself
        # costs no rules (§15.2), and a refused batch costs nothing (TEST-036).
        # Every other recorded operation was attempted and audited, so it
        # charges its logical ops. Preflight already validated the budget, so
        # debit cannot raise here; len() falls back defensively to 1.
        if error.code in {"BUDGET_INSUFFICIENT", "NODE_SCOPE_MISMATCH"}:
            charged = 0
        elif tool == "board_expand" and isinstance(arguments.get("action_ids"), list):
            charged = self._charge(tool, arguments)
        elif tool == "board_expand":
            charged = 1
            self._budget.debit(charged)
        else:
            charged = self._charge(tool, arguments)
        error_bytes = canonical_json_bytes({"error": error.model_dump(mode="json")})
        error_artifact_id = self._artifact_sink(error_bytes, "application/json")
        self._journal.settle_tool_operation(
            operation_id=operation_id,
            decision_id=self.decision_id,
            status=status,
            result_artifact_id=error_artifact_id,
            error_code=error.code,
        )
        raw_node_id: Any = arguments.get("node_id")
        node_id_for_timeline = raw_node_id if isinstance(raw_node_id, str) else ""
        if error.code != "NODE_SCOPE_MISMATCH" and node_id_for_timeline:
            # A foreign node must not be confirmed to exist in the timeline
            # (§42.6: "não retornar o conteúdo ou confirmar a existência").
            # A malformed request carries no node to expose, so it settles
            # without an observation row.
            self._exposure_sequence = self._journal.next_exposure_sequence(self.decision_id)
            self._journal.record_observation(
                observation_id=observation_id_v2(
                    sha256_hex(error_bytes), self._round_ordinal, self._exposure_sequence
                ),
                decision_id=self.decision_id,
                node_id=node_id_for_timeline,
                round_id=self._round_id,
                operation_id=operation_id,
                kind=_TOOL_KIND[tool],
                payload_artifact_id=error_artifact_id,
                semantic_hash=sha256_hex(error_bytes),
                policy_hash=self._policy_hash,
                exposure_sequence=self._exposure_sequence,
                available_before_selection=True,
            )
        return ToolEnvelope(
            ok=False,
            meta=self._meta(operation_id, charged=charged, semantic_hash=None),
            result=None,
            error=error,
        )

    def _unrecorded_failure(self, idempotency_key: str, error: ToolError) -> ToolEnvelope:
        """Failure before any operation row exists: nothing charged, nothing exposed."""
        return ToolEnvelope(
            ok=False,
            meta=self._meta(
                operation_id_v2(self.decision_id, self._round_ordinal, idempotency_key),
                charged=0,
                semantic_hash=None,
            ),
            result=None,
            error=error,
        )

    def _meta(self, operation_id: str, *, charged: int, semantic_hash: str | None) -> EnvelopeMeta:
        return EnvelopeMeta(
            decision_id=self.decision_id,
            round_id=self._round_id,
            operation_id=operation_id,
            tool_call_id=f"{self.decision_id}:{self._call_count}",
            exposure_sequence=self._exposure_sequence,
            policy_hash=self._policy_hash,
            semantic_hash=semantic_hash,
            logical_operations_charged=charged,
            physical_rules_queries=0,
            remaining_model_calls=0,
            remaining_tool_operations=self._budget.remaining,
        )


def _decode_artifact(data: bytes) -> dict[str, Any]:
    """Decode an artifact payload; a malformed stored payload is a contract violation."""
    value: Any = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("artifact payload is not a JSON object")
    return cast(dict[str, Any], value)
