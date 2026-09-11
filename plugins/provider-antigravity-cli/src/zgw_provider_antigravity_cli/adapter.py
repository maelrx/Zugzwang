"""Antigravity CLI (agy) provider adapter.

One inference call -> one `agy --print` execution in **sandbox** mode with
stream-json output. The stream is audited in real time: any shell/network/
browser/subagent tool call aborts the call fail-closed (ProviderIsolationError)
because the chess decision only needs inert text proposals. Raw stream events
are kept as wire evidence; no fallback is attempted.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    CapabilityMissingError,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.domain.provider_isolation import ProviderIsolationError
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    MessageRole,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    StopReason,
    TextPart,
    ToolCallPart,
    ToolDefinition,
    WireFidelity,
)

# Tool calls that give the model an environment (execution, network, browser,
# subagents, writes, schedules). A chess decision never needs them.
RISKY_TOOLS = frozenset(
    {
        "run_command",
        "read_url_content",
        "search_web",
        "open_browser_url",
        "execute_browser_javascript",
        "call_mcp_tool",
        "invoke_subagent",
        "define_subagent",
        "manage_subagents",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "sed_file",
        "notebook_execution",
        "notebook_edit",
        "manage_task",
        "schedule",
        "manage_inbox",
        "send_message",
        "send_command_input",
    }
)
RISKY_PREFIXES = ("browser_", "click_browser_", "capture_browser_")

_KNOWN_TOOLS = {
    "board_observe",
    "board_inspect",
    "board_expand",
    "board_compare",
    "board_finalize",
}


def _is_risky_tool(name: str) -> bool:
    return name in RISKY_TOOLS or name.startswith(RISKY_PREFIXES)


def _flatten_prompt(request: ModelRequest) -> str:
    """Flatten the canonical request into one self-contained prompt."""
    prompt_parts: list[str] = []
    for msg in request.messages:
        prefix = ""
        if msg.role is MessageRole.SYSTEM:
            prefix = "[SYSTEM INSTRUCTION]\n"
        elif msg.role is MessageRole.ASSISTANT:
            prefix = "[ASSISTANT]\n"
        elif msg.role is MessageRole.TOOL:
            prefix = "[TOOL RESULT]\n"
        chunks: list[str] = []
        for part in msg.parts:
            if isinstance(part, TextPart):
                chunks.append(part.text)
            elif isinstance(part, ToolCallPart):
                chunks.append(f"[CALL {part.tool_name}]: {json.dumps(part.arguments)}")
            elif hasattr(part, "content") and hasattr(part, "tool_name"):
                result = cast("Any", part)
                chunks.append(f"[RESULT {result.tool_name}]: {result.content}")
        if chunks:
            prompt_parts.append(f"{prefix}{''.join(chunks)}")

    if request.tools:
        lines = ["\n[AVAILABLE TOOLS]"]
        for tool in request.tools:
            typed: ToolDefinition = tool
            lines.append(f"- {typed.name}: {typed.description}")
        lines.append(
            "\nAnswer with exactly one JSON command inside a ```json block:\n"
            '```json\n{"command": "<tool_name>", "arguments": {...}}\n```\n'
            "When ready to move, finalize with:\n"
            '```json\n{"command": "board_finalize", "arguments": '
            '{"node_id": "<root_node_id>", "action_id": "<action_id>"}}\n```\n'
            "Do not use any external tool; you have no shell, network or files."
        )
        prompt_parts.append("\n".join(lines))
    return "\n\n".join(prompt_parts)


def _extract_tool_calls(text: str) -> tuple[ToolCallPart, ...]:
    """Extract tool proposals from response text (JSON block or embedded object)."""
    calls: list[ToolCallPart] = []
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    candidates: list[str] = list(blocks)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])

    for raw in candidates:
        try:
            parsed: Any = json.loads(raw)
        except Exception:
            continue
        items: list[Any] = cast("list[Any]", parsed) if isinstance(parsed, list) else [parsed]
        for item_any in items:
            if not isinstance(item_any, dict):
                continue
            item = cast("dict[str, Any]", item_any)
            tool_name = str(item.get("command") or item.get("tool") or item.get("name") or "")
            if tool_name in _KNOWN_TOOLS:
                raw_args: Any = item.get("arguments") or item.get("parameters") or {}
                args: dict[str, Any] = (
                    dict(cast("dict[str, Any]", raw_args)) if isinstance(raw_args, dict) else {}
                )
                call_id = f"call_{abs(hash(json.dumps(args, sort_keys=True))) % 1000000:06d}"
                calls.append(
                    ToolCallPart(tool_call_id=call_id, tool_name=tool_name, arguments=args)
                )
            elif "action" in item and ("node_id" in item or "node" in item):
                node = str(item.get("node_id") or item.get("node"))
                action = str(item.get("action_id") or item["action"])
                call_id = f"call_{abs(hash(action)) % 1000000:06d}"
                calls.append(
                    ToolCallPart(
                        tool_call_id=call_id,
                        tool_name="board_finalize",
                        arguments={"node_id": node, "action_id": action},
                    )
                )

    unique: list[ToolCallPart] = []
    seen: set[tuple[str, str]] = set()
    for call in calls:
        key = (call.tool_name, json.dumps(call.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            unique.append(call)
    return tuple(unique)


class AntigravityCliBackend:
    """Backend delegating one inference call to sandboxed `agy --print`."""

    backend_id = "provider.antigravity_cli"
    backend_version = "0.1.0.dev0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        model: str = "gemini-3.8-flash-low",
        executable: str | None = None,
        timeout_seconds: float = 420.0,
        reasoning_effort: str | None = None,
    ) -> None:
        self._model = model
        self._executable = executable or os.environ.get(
            "ANTIGRAVITY_AGENTAPI_EXE",
            shutil.which("agy") or "/home/maelrx/.local/bin/agy",
        )
        self._timeout_seconds = timeout_seconds
        self._reasoning_effort = reasoning_effort or "low"
        self._last_wire_request: dict[str, Any] | None = None
        self._last_wire_response: dict[str, Any] | None = None

    @property
    def descriptor(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            plugin_api=self.plugin_api,
            default_capabilities=frozenset(
                {
                    Capability.TEXT_INPUT,
                    Capability.TOOL_CALLING,
                    Capability.JSON_SCHEMA_OUTPUT,
                    Capability.REASONING_CONTROL,
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(),
            limitations=(
                "Antigravity CLI (agy) with --sandbox; tools enforced fail-closed",
                "uses the local logged-in Antigravity session (no API key)",
                "usage is provider-reported; cost stays unknown (GATE-009)",
            ),
        )

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        supported = self.descriptor.default_capabilities
        missing = frozenset(c for c in required if c not in supported)
        if missing and on_unsupported is OnUnsupported.FAIL:
            raise CapabilityMissingError(
                f"Antigravity CLI backend lacks required capabilities: {sorted(c.value for c in sorted(missing))}",
                technical_context=f"required={sorted(c.value for c in required)}",
            )
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=missing,
            missing_preferred=frozenset(c for c in preferred if c not in supported),
            on_unsupported=on_unsupported,
        )

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        prompt = _flatten_prompt(request)
        scratch = Path(tempfile.mkdtemp(prefix="zgw-agy-"))
        cmd = [
            self._executable,
            "--print",
            prompt,
            "--model",
            request.model.model,
            "--effort",
            self._reasoning_effort,
            "--sandbox",
            "--output-format",
            "stream-json",
            "--disable-slash-commands",
        ]
        constraint = request.output_constraint
        if constraint.format in {"json_schema", "json_object"}:
            schema = constraint.schema_ or {"type": "object"}
            cmd.extend(["--json-schema", json.dumps(schema, ensure_ascii=False)])
        self._last_wire_request = {
            "cmd": [part if part != prompt else f"<prompt:{len(prompt)} chars>" for part in cmd],
            "prompt_length": len(prompt),
        }
        started = utc_now()
        events: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        usage_raw: dict[str, Any] = {}
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(scratch),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "ANTIGRAVITY_CLI_HEADLESS": "1"},
            )
        except FileNotFoundError as exc:
            raise ProviderConnectionError(
                f"Antigravity CLI not found at {self._executable}",
                technical_context=f"path={self._executable}",
            ) from exc

        async def consume() -> None:
            assert process.stdout is not None
            async for raw_line in process.stdout:
                line = raw_line.decode(errors="replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    event: Any = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                row_event = cast("dict[str, Any]", event)
                events.append(row_event)
                payload = row_event.get("step_update")
                if row_event.get("event") == "step_update" and isinstance(payload, dict):
                    row = cast("dict[str, Any]", payload)
                    if row.get("step_type") == "tool":
                        tool_name = str(row.get("tool_name") or "")
                        if _is_risky_tool(tool_name):
                            raise ProviderIsolationError(
                                f"Antigravity native tool {tool_name!r} rejected; move discarded.",
                                wire_response={"events": events},
                            )
                    delta = row.get("text_delta")
                    if isinstance(delta, str) and delta:
                        text_chunks.append(delta)
                    usage = row.get("usage")
                    if isinstance(usage, dict):
                        usage_raw.update(cast("dict[str, Any]", usage))
                if row_event.get("event") == "result":
                    payload = row_event.get("result")
                    if isinstance(payload, dict):
                        row = cast("dict[str, Any]", payload)
                        usage = row.get("usage")
                        if isinstance(usage, dict):
                            usage_raw.update(cast("dict[str, Any]", usage))
                        response = row.get("response")
                        if isinstance(response, str) and response.strip() and not text_chunks:
                            text_chunks.append(response)

        try:
            async with asyncio.timeout(self._timeout_seconds):
                await consume()
                await process.wait()
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProviderTimeoutError(
                f"Antigravity CLI timed out after {self._timeout_seconds}s",
                technical_context="agy --print stream-json",
            ) from exc
        except ProviderIsolationError:
            process.kill()
            await process.wait()
            raise
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        self._last_wire_response = {"events": events}
        if process.returncode not in (0, None):
            raise ProviderResponseError(
                f"Antigravity CLI exited with code {process.returncode}",
                technical_context="agy --print",
            )

        final_text = "".join(text_chunks)
        input_tokens = int(usage_raw.get("input_tokens") or 0)
        output_tokens = int(usage_raw.get("output_tokens") or 0)
        finished = utc_now()
        normalized = NormalizedResponse(
            content_parts=(TextPart(text=final_text),) if final_text else (),
            tool_calls=_extract_tool_calls(final_text),
            stop_reason=StopReason(canonical="end_turn", raw="SUCCESS"),
            model_requested=request.model,
            model_reported=request.model.model,
            request_id=f"agy-{context.run_id}",
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                source=UsageSource.PROVIDER,
            ),
            started_at=started,
            finished_at=finished,
            adapter_version=self.backend_version,
            wire_fidelity=WireFidelity.PARTIAL,
            warnings=(),
        )
        return ProviderResult(
            response=normalized,
            wire_request=self._last_wire_request,
            wire_response=self._last_wire_response,
            wire_fidelity=WireFidelity.PARTIAL,
        )

    async def close(self) -> None:
        """No persistent daemon connection to close."""
