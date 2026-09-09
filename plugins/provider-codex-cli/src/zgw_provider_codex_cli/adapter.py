"""Codex CLI provider adapter.

Calls the local `codex` CLI in headless mode (`codex exec --json`) using the
authenticated user session. No API key is required — authentication lives in
the user's CODEX_HOME. One inference call maps to exactly one CLI invocation:
no agent loop, no cross-call context, no fallback. Usage reported by the CLI
is recorded with ``source=provider``; cost stays ``unknown`` (GATE-009).
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import os
import re
import shutil
import tempfile
from typing import Any, cast

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    CapabilityMissingError,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from zugzwang_core.domain.money import TokenUsage, UsageSource
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
    ReasoningAvailability,
    ReasoningTelemetry,
    StopReason,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    WireFidelity,
)


def _single_flight_lock(lock_path: str | None):
    """Optional cross-process single-flight gate (opt-in via config)."""
    if not lock_path:

        @contextlib.contextmanager
        def _noop():
            yield

        return _noop()

    @contextlib.contextmanager
    def _gate():
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    return _gate()


def _extract_tool_calls(text: str) -> tuple[ToolCallPart, ...]:
    """Extract tool call proposals from response text (JSON block or embedded object)."""
    calls: list[ToolCallPart] = []
    known_tools = {
        "board_observe",
        "board_inspect",
        "board_expand",
        "board_compare",
        "board_finalize",
    }

    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    candidate_strings = list(blocks)

    s = text.find("{")
    e = text.rfind("}")
    if s >= 0 and e > s:
        candidate_strings.append(text[s : e + 1])

    for raw in candidate_strings:
        try:
            parsed = json.loads(raw)
        except Exception:
            continue

        parsed_any: Any = parsed
        candidates: list[Any] = (
            cast(list[Any], parsed_any) if isinstance(parsed_any, list) else [parsed_any]
        )
        for item_any in candidates:
            if not isinstance(item_any, dict):
                continue
            item_dict = cast(dict[str, Any], item_any)
            tool_name = str(
                item_dict.get("command") or item_dict.get("tool") or item_dict.get("name") or ""
            )
            if tool_name in known_tools:
                raw_args: Any = item_dict.get("arguments") or item_dict.get("parameters") or {}
                args: dict[str, Any] = dict(cast(dict[str, Any], raw_args)) if isinstance(raw_args, dict) else {}
                reserved = {"command", "tool", "name", "arguments", "parameters"}
                for k, v in item_dict.items():
                    if k not in reserved and k not in args:
                        args[k] = v
                call_id = f"call_{abs(hash(json.dumps(args, sort_keys=True))) % 1000000:06d}"
                calls.append(
                    ToolCallPart(tool_call_id=call_id, tool_name=tool_name, arguments=args)
                )
            elif "action" in item_dict and ("node_id" in item_dict or "node" in item_dict):
                node = str(item_dict.get("node_id") or item_dict.get("node"))
                action = str(item_dict.get("action_id") or item_dict["action"])
                call_id = f"call_{abs(hash(action)) % 1000000:06d}"
                calls.append(
                    ToolCallPart(
                        tool_call_id=call_id,
                        tool_name="board_finalize",
                        arguments={"node_id": node, "action_id": action},
                    )
                )

    unique_calls: list[ToolCallPart] = []
    seen: set[tuple[str, str]] = set()
    for c in calls:
        key = (c.tool_name, json.dumps(c.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            unique_calls.append(c)

    return tuple(unique_calls)


def _flatten_prompt(request: ModelRequest) -> str:
    """Flatten the canonical request into one prompt (antigravity tool contract)."""
    prompt_parts: list[str] = []
    for msg in request.messages:
        prefix = ""
        if msg.role is MessageRole.SYSTEM:
            prefix = "[SYSTEM INSTRUCTION]\n"
        elif msg.role is MessageRole.ASSISTANT:
            prefix = "[ASSISTANT]\n"
        elif msg.role is MessageRole.TOOL:
            prefix = "[TOOL RESULT]\n"

        text_chunks: list[str] = []
        for p in msg.parts:
            if isinstance(p, TextPart):
                text_chunks.append(p.text)
            elif isinstance(p, ToolCallPart):
                text_chunks.append(f"[CALL {p.tool_name}]: {json.dumps(p.arguments)}")
            elif isinstance(p, ToolResultPart):
                text_chunks.append(f"[RESULT {p.tool_name}]: {p.content}")
        if text_chunks:
            prompt_parts.append(f"{prefix}{''.join(text_chunks)}")

    if request.tools:
        tool_lines = ["\n[AVAILABLE TOOLS]"]
        for td in request.tools:
            tool_lines.append(f"- {td.name}: {td.description}")
        tool_lines.append(
            "\nTo execute a tool, your response MUST contain a JSON command:\n"
            '```json\n{"command": "<tool_name>", "arguments": {...}}\n```\n'
            "When you are ready to make the move, finalize with:\n"
            '```json\n{"command": "board_finalize", "arguments": {"node_id": "<root_node_id>", "action_id": "<action_id>"}}\n```'
        )
        prompt_parts.append("\n".join(tool_lines))

    return "\n\n".join(prompt_parts)


class CodexCliBackend:
    """Backend delegating inference to headless `codex exec` (logged-in session)."""

    backend_id = "provider.codex_cli"
    backend_version = "0.1.0.dev0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        model: str = "gpt-6-astra",
        executable: str | None = None,
        timeout_seconds: float = 300.0,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        single_flight_lock: str | None = None,
    ) -> None:
        self._model = model
        self._executable = executable or os.environ.get(
            "CODEX_CLI_EXE", shutil.which("codex") or "/home/maelrx/.local/bin/codex"
        )
        self._timeout_seconds = timeout_seconds
        self._reasoning_effort = reasoning_effort
        self._max_output_tokens = max_output_tokens
        self._single_flight_lock = single_flight_lock

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
                    Capability.REASONING_CONTROL,
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(),
            limitations=(
                "Codex CLI headless (`codex exec`) local execution",
                "uses the logged-in Codex session (no API key in manifests)",
                "the CLI injects its own system context (~30k input tokens per call)",
                "cost not claimed (GATE-009 pending)",
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
                f"Codex CLI backend lacks required capabilities: {sorted(c.value for c in missing)}",
                technical_context=f"required={sorted(c.value for c in required)}",
            )
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=missing,
            missing_preferred=frozenset(c for c in preferred if c not in supported),
        )

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        started = utc_now()
        prompt = _flatten_prompt(request)

        effective_model = (
            request.model.model if request.model and request.model.model else self._model
        )
        scratch = tempfile.mkdtemp(prefix="zgw-codex-")
        cmd = [
            self._executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--color",
            "never",
            "-s",
            "read-only",
            "-C",
            scratch,
            "-m",
            effective_model,
        ]
        if self._reasoning_effort:
            cmd.extend(["-c", f"model_reasoning_effort={self._reasoning_effort}"])
        if self._max_output_tokens:
            cmd.extend(["-c", f"model_max_output_tokens={int(self._max_output_tokens)}"])
        cmd.append(prompt)

        wire_request: dict[str, Any] = {
            "cmd": cmd[:-1],
            "model": effective_model,
            "prompt_length": len(prompt),
            "attempt_id": context.attempt_id,
        }

        gate = _single_flight_lock(self._single_flight_lock)

        async def _run() -> tuple[asyncio.subprocess.Process, bytes, bytes]:
            child = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(child.communicate(), timeout=self._timeout_seconds)
            return child, out, err

        try:
            with gate:
                proc, stdout, stderr = await _run()
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Codex CLI timed out after {self._timeout_seconds}s",
                technical_context=f"cmd={cmd[0]} exec",
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderConnectionError(
                f"Codex CLI binary not found at {self._executable}",
                technical_context=f"path={self._executable}",
            ) from exc
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise ProviderResponseError(
                f"Codex CLI exited with code {proc.returncode}: {err_msg[:300]}",
                technical_context=f"code={proc.returncode}",
            )

        events: list[dict[str, Any]] = []
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(cast(dict[str, Any], parsed))

        response_text: str | None = None
        usage_raw: dict[str, Any] = {}
        error_items: list[str] = []
        for ev in events:
            kind = ev.get("type")
            item = ev.get("item")
            if kind == "item.completed" and isinstance(item, dict):
                item_dict = cast(dict[str, Any], item)
                if item_dict.get("type") == "agent_message":
                    text = item_dict.get("text")
                    if isinstance(text, str) and text.strip():
                        response_text = text
                elif item_dict.get("type") == "error":
                    message = item_dict.get("message")
                    if isinstance(message, str):
                        error_items.append(message)
            elif kind == "turn.completed" and isinstance(ev.get("usage"), dict):
                usage_raw = cast(dict[str, Any], ev["usage"])

        if response_text is None:
            detail = "; ".join(error_items[-2:]) or "no agent_message in codex events"
            raise ProviderResponseError(
                f"Codex CLI produced no agent message: {detail[:300]}",
                technical_context=f"events={len(events)}",
            )

        in_tokens = int(usage_raw.get("input_tokens") or 0)
        out_tokens = int(usage_raw.get("output_tokens") or 0)
        reasoning_tokens_raw = usage_raw.get("reasoning_output_tokens")
        reasoning_tokens = (
            int(reasoning_tokens_raw)
            if isinstance(reasoning_tokens_raw, int) and reasoning_tokens_raw >= 0
            else None
        )
        token_usage = TokenUsage(
            input_tokens=in_tokens + int(usage_raw.get("cached_input_tokens") or 0),
            output_tokens=out_tokens,
            source=UsageSource.PROVIDER,
        )

        tool_calls = _extract_tool_calls(response_text)
        warnings = tuple(f"codex item error (non-fatal): {m[:160]}" for m in error_items)

        telemetry = ReasoningTelemetry(
            provider="codex-cli",
            model=effective_model,
            usage=usage_raw,
            reasoning_tokens=reasoning_tokens,
            reasoning_items=(),
            reasoning_summary=None,
            availability=ReasoningAvailability(
                reasoning_tokens=reasoning_tokens is not None,
                reasoning_items=False,
                reasoning_summary=False,
            ),
            wire_fidelity=WireFidelity.PARTIAL,
            provider_metadata={"event_types": [str(ev.get("type")) for ev in events]},
        )

        norm = NormalizedResponse(
            content_parts=(TextPart(text=response_text),),
            tool_calls=tool_calls,
            stop_reason=StopReason(canonical="end_turn"),
            model_requested=request.model,
            model_reported=effective_model,
            request_id="",
            usage=token_usage,
            started_at=started,
            finished_at=utc_now(),
            adapter_version=self.backend_version,
            wire_fidelity=WireFidelity.PARTIAL,
            warnings=warnings,
        )

        return ProviderResult(
            response=norm,
            wire_request=wire_request,
            wire_response={"events": events},
            reasoning_telemetry=telemetry,
            wire_fidelity=WireFidelity.PARTIAL,
        )

    async def close(self) -> None:
        """No persistent daemon connection to close."""
        return None
