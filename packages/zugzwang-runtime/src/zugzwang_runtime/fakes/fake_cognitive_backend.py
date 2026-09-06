"""Fake cognitive ModelBackend: scripted proposals behind the typed port.

Scripts belong HERE, never in the productive loop (ZGW-0101): the loop calls
``infer`` with a canonical ModelRequest, and this backend turns its script
into ``ProviderResult`` responses the same way a real adapter would. Script
entries may be dicts (``{"tool", "arguments"}``) or callables receiving the
request messages — the causal TEST-023 probe uses a callable to extract the
``child_node_id`` produced in round N from the actual round-N+1 request,
proving the feedback is real and not trace-window dressing.

Two interaction modes exercise the same semantic effect (TEST-026/027):
``native_tools`` emits ``ToolCallPart`` responses; ``json_commands`` emits a
JSON command inside a text part.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from zugzwang_core.domain.money import TokenUsage
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    Message,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    StopReason,
    TextPart,
    ToolCallPart,
)
from zugzwang_core.ports.model import WireFidelity as _WireFidelityLike

ScriptEntry = dict[str, Any] | Callable[[list[Message]], dict[str, Any]]


class ScriptExhausted(RuntimeError):
    """The script ran out before the loop stopped: a test design error."""


class FakeCognitiveBackend:
    """ModelBackend port implementation driven by a fixed proposal script."""

    def __init__(
        self,
        script: list[ScriptEntry],
        *,
        interaction_mode: str = "native_tools",
        model: str = "scripted",
        usage: TokenUsage | None = None,
    ) -> None:
        if interaction_mode not in {"native_tools", "json_commands"}:
            raise ValueError("interaction_mode must be native_tools or json_commands")
        self._script = list(script)
        self._interaction_mode = interaction_mode
        self._model = model
        self._usage = usage or TokenUsage(input_tokens=17, output_tokens=9)
        self.calls = 0
        self.seen_requests: list[ModelRequest] = []

    @property
    def descriptor(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="fake.cognitive",
            backend_version="0.1.0",
            plugin_api="zgw.plugin/v1alpha1",
            default_capabilities=frozenset({Capability.TEXT_INPUT}),
            limitations=("scripted proposals only; no network, no engine",),
        )

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        supported = frozenset({Capability.TEXT_INPUT})
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=frozenset(required - supported),
            missing_preferred=frozenset(preferred - supported),
            on_unsupported=on_unsupported,
        )

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        self.calls += 1
        self.seen_requests.append(request)
        if self.calls > len(self._script):
            raise ScriptExhausted(
                f"script exhausted after {len(self._script)} entries; the loop kept calling infer"
            )
        entry: Any = self._script[self.calls - 1]
        if callable(entry):
            entry = entry(list(request.messages))
        proposal_tool = str(entry["tool"])
        arguments = dict(entry.get("arguments") or {})
        if self._interaction_mode == "native_tools":
            return ProviderResult(
                response=NormalizedResponse(
                    content_parts=(),
                    tool_calls=(
                        ToolCallPart(
                            tool_call_id=f"call_{self.calls}",
                            tool_name=proposal_tool,
                            arguments=arguments,
                        ),
                    ),
                    stop_reason=StopReason(canonical="tool_calls", raw="script"),
                    model_requested=request.model,
                    model_reported=request.model.model,
                    usage=self._usage,
                    adapter_version="fake-cognitive/0.1.0",
                ),
                wire_fidelity=_WireFidelityLike.FULL,
            )
        command = json.dumps(
            {"command": proposal_tool, "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
        )
        return ProviderResult(
            response=NormalizedResponse(
                content_parts=(TextPart(text=command),),
                tool_calls=(),
                stop_reason=StopReason(canonical="end_turn", raw="script"),
                model_requested=request.model,
                model_reported=request.model.model,
                usage=self._usage,
                adapter_version="fake-cognitive/0.1.0",
            ),
        )


def tool_result_parts(messages: list[Message], tool_name: str | None = None) -> list[Any]:
    """Every ToolResultPart in the request so far, in order."""
    parts: list[Any] = []
    for message in messages:
        for part in message.parts:
            if getattr(part, "type", None) == "tool_result" and (
                tool_name is None or getattr(part, "tool_name", None) == tool_name
            ):
                parts.append(part)
    return parts


def extract_child_node_id(content: str, index: int = 0) -> str | None:
    """Pull the Nth child_node_id out of a board_expand ToolResult payload."""
    try:
        payload: Any = json.loads(content)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    record = cast(dict[str, Any], payload)
    results: Any = record.get("results")
    if not isinstance(results, list):
        return None
    items = cast("list[Any]", results)
    if index >= len(items):
        return None
    row = cast("dict[str, Any]", items[index])
    child = row.get("child_node_id")
    return child if isinstance(child, str) else None
