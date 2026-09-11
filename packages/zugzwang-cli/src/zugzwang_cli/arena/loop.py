"""Arena decision loop: the campaign wire protocol, minus run machinery.

Mirrors ``zugzwang_runtime.cognition.loop.CognitiveLoop`` for native_tools
(the mode every winning ZGX fullgame used): same system prompt, same
``board_*`` tool definitions, root preload, inline child packages, finalize
on the ROOT node, fail-closed on exhausted rounds. What is intentionally NOT
here: journals, budgets, CAS artifacts — the arena keeps its own verbatim
call log instead, which satisfies attribution per call.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, cast

import chess

from zugzwang_chess.environment.standard import ChessGameState
from zugzwang_core.domain.errors import (
    ProviderThrottlingError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from zugzwang_core.domain.provider_isolation import ProviderIsolationError, reject_native_execution
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    ProviderResult,
    TextPart,
    ToolCallPart,
    ToolResultPart,
)
from zugzwang_runtime.cognition.loop import BOARD_TOOL_DEFINITIONS, FINALIZE_TOOL
from zugzwang_runtime.execution.evidence import sanitize_wire_payload

from .positions import BoardFacade

DEFAULT_DIRECTIVE = (
    "TACTICAL PRIORITIES & FACTUAL MEMORY: On every turn, examine all "
    "forcing lines (checks, captures, immediate threats). Expand candidates "
    "to verify tactical safety. Retain factual tactical memory across rounds "
    "to avoid blunders. Finalize on ROOT via board_finalize once your "
    "candidate survives verification."
)

ROOT_NODE_ID = "n0"


@dataclass(slots=True)
class _Node:
    node_id: str
    state: Any
    depth: int
    root_action: str | None
    parent_node_id: str | None
    terminal: bool


@dataclass(slots=True)
class ModelCallInfo:
    round_ordinal: int
    ok: bool
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    failure: str | None = None


@dataclass(slots=True)
class DecisionOutcome:
    status: str  # COMMITTED | PROVIDER_* | NO_FINALIZE | PROTOCOL_ERROR
    uci: str | None = None
    final_text: str = ""
    calls: list[ModelCallInfo] = field(default_factory=list["ModelCallInfo"])
    rounds_used: int = 0
    protocol_errors: int = 0
    error: str | None = None


@dataclass(slots=True)
class _Proposal:
    provider_tool_call_id: str
    tool: str
    arguments: dict[str, Any]


def _json_command(text: str) -> dict[str, Any] | None:
    """One JSON command from prose (json_commands fallback); malformed -> None."""
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


class ArenaDecisionLoop:
    """One model turn over one position, bounded rounds, fail closed."""

    def __init__(
        self,
        *,
        game_id: str,
        board: BoardFacade,
        backend: Any,
        model_ref: ModelRef,
        max_rounds: int = 6,
        directive: str | None = None,
        prior_note: dict[str, Any] | None = None,
        call_sink: Any = None,
        progress_sink: Any = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._game_id = game_id
        self._board = board
        self._backend = backend
        self._model_ref = model_ref
        self._max_rounds = max_rounds
        self._directive = (
            directive.strip() if isinstance(directive, str) and directive.strip() else None
        )
        self._prior_note = prior_note if isinstance(prior_note, dict) and prior_note else None
        self._call_sink = call_sink
        self._progress_sink = progress_sink
        self._nodes: dict[str, _Node] = {}

    def _progress(self, kind: str, **details: Any) -> None:
        if self._progress_sink is not None:
            with contextlib.suppress(Exception):
                self._progress_sink({"kind": kind, **details})

    # -- node bookkeeping ---------------------------------------------------------

    def _register_root(self, state: Any) -> _Node:
        node = _Node(
            node_id=ROOT_NODE_ID,
            state=state,
            depth=0,
            root_action=None,
            parent_node_id=None,
            terminal=state.terminal,
        )
        self._nodes[ROOT_NODE_ID] = node
        return node

    def _mint_child(self, parent: _Node, uci: str, state: Any) -> _Node:
        node_id = f"n{len(self._nodes)}::{uci}"
        node = _Node(
            node_id=node_id,
            state=state,
            depth=parent.depth + 1,
            root_action=parent.root_action or uci,
            parent_node_id=parent.node_id,
            terminal=state.terminal,
        )
        self._nodes[node_id] = node
        return node

    # -- tool execution (broker envelope shapes) ----------------------------------

    def _execute(self, proposal: _Proposal) -> dict[str, Any]:
        tool = proposal.tool
        arguments = proposal.arguments
        if tool == "board_observe":
            node = self._nodes.get(str(arguments.get("node_id", "")))
            if node is None:
                return {
                    "ok": False,
                    "error": {"code": "NODE_SCOPE_MISMATCH", "message": "unknown node_id"},
                }
            packet = self._board.packet(
                node.state, node.node_id, cursor=int(arguments.get("cursor", 0) or 0)
            )
            return {
                "ok": True,
                "result": {
                    "packet": packet.model_dump(mode="json"),
                    "content_hash": packet.content_hash(),
                },
            }
        if tool == "board_inspect":
            node = self._nodes.get(str(arguments.get("node_id", "")))
            if node is None:
                return {
                    "ok": False,
                    "error": {"code": "NODE_SCOPE_MISMATCH", "message": "unknown node_id"},
                }
            packet = self._board.packet(node.state, node.node_id)
            query = str(arguments.get("query", "terminal"))
            facts: dict[str, Any] = {"terminal": packet.terminal.model_dump(mode="json")}
            if query in {"relations", "complete"}:
                facts["relations"] = [dict(item) for item in packet.relations.items]
            return {
                "ok": True,
                "result": {"facts": facts, "complete": True, "content_hash": packet.content_hash()},
            }
        if tool == "board_expand":
            return self._expand(str(arguments.get("node_id", "")), arguments.get("action_ids"))
        if tool == "board_compare":
            node = self._nodes.get(str(arguments.get("node_id", "")))
            other = self._nodes.get(str(arguments.get("other_node_id", "")))
            if node is None or other is None:
                return {
                    "ok": False,
                    "error": {"code": "NODE_SCOPE_MISMATCH", "message": "unknown node_id"},
                }
            return {
                "ok": True,
                "result": {
                    "formal_differences": self._compare(node, other),
                    "content_hash": self._board.packet(node.state, node.node_id).content_hash(),
                },
            }
        return {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": f"unknown tool {tool!r}"}}

    def _expand(self, node_id: str, action_ids: Any) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        if node is None:
            return {
                "ok": False,
                "error": {"code": "NODE_SCOPE_MISMATCH", "message": "unknown node_id"},
            }
        if not isinstance(action_ids, list):
            return {
                "ok": False,
                "error": {"code": "INVALID_ARGUMENTS", "message": "action_ids must be strings"},
            }
        refs: list[str] = []
        for raw_item in cast("list[object]", action_ids):
            if not isinstance(raw_item, str):
                return {
                    "ok": False,
                    "error": {"code": "INVALID_ARGUMENTS", "message": "action_ids must be strings"},
                }
            refs.append(raw_item)
        entries = {action_id: uci for uci, action_id in self._board.legal_entries(node.state)}
        results: list[dict[str, Any]] = []
        for action_id in refs:
            uci = entries.get(action_id)
            if uci is None:
                return {
                    "ok": False,
                    "error": {
                        "code": "ACTION_STATE_MISMATCH",
                        "message": f"action id not in the legal set: {action_id!r}",
                    },
                }
            child_board_state = node.state.to_board()
            child_board_state.push(chess.Move.from_uci(uci))
            child_state = ChessGameState(
                fen=child_board_state.fen(),
                initial_fen=node.state.initial_fen,
                move_stack=(*node.state.move_stack, uci),
                variant=node.state.variant,
            )
            child = self._mint_child(node, uci, child_state)
            child_packet = self._board.packet(child_state, child.node_id)
            row: dict[str, Any] = {
                "action_id": action_id,
                "uci": uci,
                "expanded": True,
                "parent_node_id": node.node_id,
                "child_node_id": child.node_id,
                "state_key": child_packet.state.state_key,
                "depth": child.depth,
                "root_action": child.root_action,
                "terminal": child.terminal,
                "edge_id": f"{node.node_id}->{uci}",
                "package": child_packet.model_dump(mode="json"),
                "package_content_hash": child_packet.content_hash(),
            }
            results.append(row)
        packet = self._board.packet(node.state, node.node_id)
        return {"ok": True, "result": {"results": results, "content_hash": packet.content_hash()}}

    def _compare(self, node: _Node, other: _Node) -> dict[str, Any]:
        return {
            "semantics_version": "arena-compare/v1",
            "kind": "adjacent"
            if other.parent_node_id == node.node_id or node.parent_node_id == other.node_id
            else "arbitrary",
            "nodes": [
                {
                    "node_id": node.node_id,
                    "fen": node.state.fen,
                    "depth": node.depth,
                    "root_action": node.root_action,
                    "terminal": node.terminal,
                },
                {
                    "node_id": other.node_id,
                    "fen": other.state.fen,
                    "depth": other.depth,
                    "root_action": other.root_action,
                    "terminal": other.terminal,
                },
            ],
        }

    # -- request building (identical shapes to the campaign loop) ------------------

    def _transcript_message_pair(self, entry: dict[str, Any]) -> tuple[Message, Message]:
        raw_arguments = entry.get("arguments")
        arguments: dict[str, Any] = (
            dict(cast("dict[str, Any]", raw_arguments)) if isinstance(raw_arguments, dict) else {}
        )
        call = Message(
            role=MessageRole.ASSISTANT,
            parts=(
                ToolCallPart(
                    tool_call_id=str(entry.get("tool_call_id", "")),
                    tool_name=str(entry.get("tool", "")),
                    arguments=arguments,
                ),
            ),
        )
        content = entry.get("result") if entry.get("ok") else entry.get("error")
        text = (
            content.decode("utf-8")
            if isinstance(content, bytes)
            else json.dumps(content, sort_keys=True, separators=(",", ":"))
        )
        outcome = Message(
            role=MessageRole.TOOL,
            parts=(
                ToolResultPart(
                    tool_call_id=str(entry.get("tool_call_id", "")),
                    tool_name=str(entry.get("tool", "")),
                    content=text,
                    is_error=not bool(entry.get("ok")),
                ),
            ),
        )
        return call, outcome

    def _system_prompt(self, ordinal: int) -> str:
        calls_used = ordinal - 2
        calls_left = max(0, self._max_rounds - calls_used)
        budget_note = (
            f" This is model call {calls_used + 1} of at most {self._max_rounds}: "
            f"{calls_left} call(s) remain including this one. "
            "The final call accepts only board_finalize — exploration then "
            "is refused, so finalize no later than the last call."
        )
        preload_note = (
            " The root observation (and any preloaded root expansions with "
            "their child packages) are ALREADY in this conversation as "
            "harness tool results — do not re-observe the root."
        )
        base = (
            "You are navigating one decision's hypothetical search graph. "
            f"The root node id is {ROOT_NODE_ID!r}: use it as node_id to observe "
            "the initial position. "
            "Use the board tools to observe the root, expand legal actions "
            "(action ids come from observations), and when ready call "
            f"{FINALIZE_TOOL} with the ROOT node and the chosen action_id. "
            "board_expand returns each child's position package INLINE in "
            "its result — you do not need to observe a child to know it, "
            "and you may call board_expand on a child node to investigate "
            "the adversary's reply (a grandchild) before finalizing."
            f"{preload_note}{budget_note}"
        )
        sections: list[str] = []
        if self._prior_note:
            lines = [
                f"- {key}: {value}"
                for key, value in self._prior_note.items()
                if value not in (None, "")
            ]
            if lines:
                sections.append(
                    "PRIOR MOVE NOTE (structured; formal facts from this "
                    "game's record plus your own last reasoning summary — "
                    "a hypothesis, not an order; verify it still applies):\n" + "\n".join(lines)
                )
        if self._directive:
            sections.append(f"OPERATOR DIRECTIVE (directed test): {self._directive}")
        return f"{base}\n\n{'\n\n'.join(sections)}" if sections else base

    def _request(self, ordinal: int, transcript: list[dict[str, Any]]) -> ModelRequest:
        messages: list[Message] = [
            Message(role=MessageRole.SYSTEM, parts=(TextPart(text=self._system_prompt(ordinal)),))
        ]
        for entry in transcript:
            call, outcome = self._transcript_message_pair(entry)
            messages.append(call)
            messages.append(outcome)
        return ModelRequest(
            model=self._model_ref,
            messages=tuple(messages),
            tools=BOARD_TOOL_DEFINITIONS,
            metadata={
                "game_id": self._game_id,
                "round_ordinal": ordinal,
                "interaction_mode": "native_tools",
            },
        )

    def _context(self, ordinal: int) -> CallContext:
        return CallContext(
            run_id=f"arena-{self._game_id}",
            step_id=f"arena-{self._game_id}:round-{ordinal:04d}",
            attempt_id=f"arena-{self._game_id}:{ordinal:04d}",
            fingerprint=f"arena:{self._game_id}:{ROOT_NODE_ID}",
        )

    # -- parsing -------------------------------------------------------------------

    def _proposals(self, response: NormalizedResponse, ordinal: int) -> list[_Proposal]:
        proposals: list[_Proposal] = []
        for index, call in enumerate(response.tool_calls):
            proposals.append(
                _Proposal(
                    provider_tool_call_id=call.tool_call_id or f"r{ordinal:04d}:native:{index}",
                    tool=call.tool_name,
                    arguments=dict(call.arguments),
                )
            )
        if not proposals:
            text = response.text().strip()
            if text:
                command = _json_command(text)
                if command is not None:
                    tool = str(command.get("command", ""))
                    raw = command.get("arguments")
                    proposals.append(
                        _Proposal(
                            provider_tool_call_id=f"r{ordinal:04d}:json:0",
                            tool=tool,
                            arguments=dict(cast("dict[str, Any]", raw))
                            if isinstance(raw, dict)
                            else {},
                        )
                    )
        return proposals

    # -- main loop -----------------------------------------------------------------

    async def run(self) -> DecisionOutcome:
        outcome = DecisionOutcome(status="RUNNING")
        protocol_errors = 0
        transcript: list[dict[str, Any]] = []
        self._progress("preparing")
        root = self._register_root(self._board.state)

        # Root preload rides in the first request as a harness tool result.
        preload = _Proposal(
            provider_tool_call_id="harness:preload-root",
            tool="board_observe",
            arguments={"node_id": ROOT_NODE_ID},
        )
        transcript.append(
            {
                "tool_call_id": preload.provider_tool_call_id,
                "tool": preload.tool,
                "arguments": dict(preload.arguments),
                **self._execute(preload),
            }
        )

        last_text = ""
        for ordinal in range(2, self._max_rounds + 2):
            outcome.rounds_used = ordinal - 1
            rounds_left = self._max_rounds + 2 - ordinal
            reserving = rounds_left <= 1
            request = self._request(ordinal, transcript)

            self._progress("waiting", round=ordinal - 1)
            started = time.monotonic()
            try:
                streamed = getattr(self._backend, "infer_with_progress", None)
                if callable(streamed) and self._progress_sink is not None:
                    observe = cast(
                        "Callable[[ModelRequest, CallContext, Callable[[dict[str, Any]], None]], Awaitable[ProviderResult]]",
                        streamed,
                    )

                    def on_summary(
                        summary: dict[str, Any], round_number: int = ordinal - 1
                    ) -> None:
                        self._progress("summary", round=round_number, **summary)

                    response: ProviderResult = await observe(
                        request, self._context(ordinal), on_summary
                    )
                else:
                    response = await self._backend.infer(request, self._context(ordinal))
                reject_native_execution(response.wire_response)
            except ProviderIsolationError as exc:
                return self._provider_failure(
                    outcome, ordinal, request, "provider_isolation_violation", exc, started
                )
            except ProviderTimeoutError as exc:
                return self._provider_failure(
                    outcome, ordinal, request, "provider_timeout_unknown", exc, started
                )
            except ProviderThrottlingError as exc:
                return self._provider_failure(
                    outcome, ordinal, request, "provider_throttling", exc, started
                )
            except ProviderTransportError as exc:
                return self._provider_failure(
                    outcome, ordinal, request, "provider_transport", exc, started
                )
            latency_ms = int((time.monotonic() - started) * 1000)

            self._progress("received", round=ordinal - 1)
            # Only explicitly labelled summaries; some adapters also keep raw
            # reasoning in telemetry, so never forward the combined text field.
            telemetry = response.reasoning_telemetry
            if telemetry:
                for index, item in enumerate(telemetry.reasoning_items):
                    if item.get("type") == "reasoning_summary" and isinstance(
                        item.get("text"), str
                    ):
                        self._progress(
                            "summary",
                            round=ordinal - 1,
                            id=f"summary-{index}",
                            text=item["text"],
                            source=telemetry.provider,
                        )
            normalized = response.response
            usage = normalized.usage
            outcome.calls.append(
                ModelCallInfo(
                    round_ordinal=ordinal - 1,
                    ok=True,
                    latency_ms=latency_ms,
                    input_tokens=usage.input_tokens or None,
                    output_tokens=usage.output_tokens or None,
                )
            )
            self._sink(ordinal, request, response, latency_ms, None)
            last_text = normalized.text()

            proposals = self._proposals(normalized, ordinal)
            finalize = next((p for p in proposals if p.tool == FINALIZE_TOOL), None)
            if reserving and finalize is None:
                outcome.status = "NO_FINALIZE"
                outcome.error = "finalize reserve reached; exploration must not consume it"
                return outcome
            if finalize is not None:
                for proposal in proposals:
                    if proposal is finalize:
                        break
                    executed = self._execute(proposal)
                    self._progress(
                        "tool", round=ordinal - 1, tool=proposal.tool, ok=bool(executed.get("ok"))
                    )
                    transcript.append(_entry(proposal, executed, ordinal))
                    if not executed.get("ok"):
                        protocol_errors += 1
                uci = self._commit(root, finalize)
                if uci is None:
                    executed = self._execute_final_error(finalize)
                    transcript.append(_entry(finalize, executed, ordinal))
                    protocol_errors += 1
                    if protocol_errors >= 3:
                        outcome.status = "PROTOCOL_ERROR"
                        outcome.error = "finalize kept refusing a legal action"
                        outcome.protocol_errors = protocol_errors
                        return outcome
                    continue
                self._progress("selected", round=ordinal - 1)
                outcome.status = "COMMITTED"
                outcome.uci = uci
                outcome.final_text = last_text
                outcome.protocol_errors = protocol_errors
                return outcome

            for proposal in proposals:
                executed = self._execute(proposal)
                self._progress(
                    "tool", round=ordinal - 1, tool=proposal.tool, ok=bool(executed.get("ok"))
                )
                transcript.append(_entry(proposal, executed, ordinal))
                if not executed.get("ok"):
                    protocol_errors += 1
            if protocol_errors >= 3:
                outcome.status = "PROTOCOL_ERROR"
                outcome.error = "protocol error ceiling reached"
                outcome.protocol_errors = protocol_errors
                return outcome

        outcome.status = "NO_FINALIZE"
        outcome.error = "round budget exhausted without finalization"
        outcome.protocol_errors = protocol_errors
        return outcome

    def _commit(self, root: _Node, finalize: _Proposal) -> str | None:
        node_id = str(finalize.arguments.get("node_id", ""))
        action_ref = str(finalize.arguments.get("action_id", ""))
        if node_id != root.node_id:
            return None
        return self._board.resolve_action(root.state, action_ref)

    def _execute_final_error(self, finalize: _Proposal) -> dict[str, Any]:
        node_id = str(finalize.arguments.get("node_id", ""))
        if node_id != ROOT_NODE_ID:
            return {
                "ok": False,
                "error": {
                    "code": "NODE_SCOPE_MISMATCH",
                    "message": "board_finalize must address the ROOT node",
                },
            }
        return {
            "ok": False,
            "error": {
                "code": "ACTION_STATE_MISMATCH",
                "message": "action does not belong to the root legal set",
            },
        }

    def _provider_failure(
        self,
        outcome: DecisionOutcome,
        ordinal: int,
        request: ModelRequest,
        failure_class: str,
        exc: Exception,
        started: float,
    ) -> DecisionOutcome:
        latency_ms = int((time.monotonic() - started) * 1000)
        outcome.calls.append(
            ModelCallInfo(
                round_ordinal=ordinal - 1, ok=False, latency_ms=latency_ms, failure=failure_class
            )
        )
        self._sink(
            ordinal,
            request,
            None,
            latency_ms,
            f"{failure_class}: {exc}",
            failure_wire=getattr(exc, "wire_response", None),
        )
        outcome.status = failure_class.upper()
        outcome.error = str(exc)[:300]
        return outcome

    def _sink(
        self,
        ordinal: int,
        request: ModelRequest,
        response: ProviderResult | None,
        latency_ms: int,
        failure: str | None,
        failure_wire: Any = None,
    ) -> None:
        if self._call_sink is None:
            return
        record: dict[str, Any] = {
            "game_id": self._game_id,
            "round_ordinal": ordinal,
            "latency_ms": latency_ms,
            "failure": failure,
            "request": _request_evidence(request),
            "response_text": response.response.text() if response is not None else None,
            "tool_calls": [
                {"tool_name": call.tool_name, "arguments": dict(call.arguments)}
                for call in (response.response.tool_calls if response is not None else ())
            ],
            "usage": (
                {
                    "input_tokens": response.response.usage.input_tokens,
                    "output_tokens": response.response.usage.output_tokens,
                    "source": str(response.response.usage.source),
                }
                if response is not None
                else None
            ),
            "model_reported": response.response.model_reported if response is not None else None,
            "wire_request": sanitize_wire_payload(
                response.wire_request
                if response is not None
                else getattr(self._backend, "_last_wire_request", None)
            ),
            "wire_response": sanitize_wire_payload(
                response.wire_response
                if response is not None
                else failure_wire
                if failure_wire is not None
                else getattr(self._backend, "_last_wire_response", None)
            ),
        }
        # Evidence writing never breaks play.
        with contextlib.suppress(Exception):
            self._call_sink(record)


def _entry(proposal: _Proposal, executed: dict[str, Any], ordinal: int) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "tool_call_id": f"{proposal.provider_tool_call_id}",
        "tool": proposal.tool,
        "arguments": dict(proposal.arguments),
        "round_ordinal": ordinal,
    }
    if executed.get("ok"):
        entry["result"] = executed.get("result")
        entry["ok"] = True
    else:
        entry["error"] = executed.get("error")
        entry["ok"] = False
    return entry


def _request_evidence(request: ModelRequest) -> dict[str, Any]:
    """Compact but complete request evidence: every message, verbatim."""
    messages: list[dict[str, Any]] = []
    for message in request.messages:
        parts: list[dict[str, Any]] = []
        for part in message.parts:
            if isinstance(part, TextPart):
                parts.append({"kind": "text", "text": part.text})
            elif isinstance(part, ToolCallPart):
                parts.append(
                    {"kind": "tool_call", "tool": part.tool_name, "arguments": dict(part.arguments)}
                )
            elif isinstance(part, ToolResultPart):
                parts.append(
                    {
                        "kind": "tool_result",
                        "tool": part.tool_name,
                        "content": part.content,
                        "is_error": part.is_error,
                    }
                )
        messages.append(
            {
                "role": str(message.role.value)
                if hasattr(message.role, "value")
                else str(message.role),
                "parts": parts,
            }
        )
    return {
        "model": str(request.model),
        "messages": messages,
        "tools": [tool.name for tool in request.tools],
    }


__all__ = [
    "DEFAULT_DIRECTIVE",
    "ROOT_NODE_ID",
    "ArenaDecisionLoop",
    "DecisionOutcome",
    "ModelCallInfo",
]
