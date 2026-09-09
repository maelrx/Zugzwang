"""Contract tests for the Codex CLI provider adapter.

Runs offline against a fake `codex` executable script: no network, no real CLI,
no secrets (ADR-031). The fake emits canned `codex exec --json` JSONL events.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from zgw_provider_codex_cli.adapter import CodexCliBackend

from zugzwang_core.domain.errors import (
    CapabilityMissingError,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from zugzwang_core.ports.model import (
    CallContext,
    Capability,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    TextPart,
    ToolDefinition,
)

CANNED_EVENTS = """{"type":"thread.started","thread_id":"th_1"}
{"type":"item.completed","item":{"id":"i0","type":"error","message":"Skill descriptions were shortened to fit the skills context budget."}}
{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"```json\\n{\\"command\\": \\"board_expand\\", \\"arguments\\": {\\"node_id\\": \\"ROOT\\"}}\\n```"}}
{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":50,"cache_write_input_tokens":0,"output_tokens":10,"reasoning_output_tokens":4}}
"""


def _write_fake_codex(tmp_path: Path, body: str) -> str:
    exe = tmp_path / "fake-codex"
    exe.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    exe.chmod(0o755)
    return str(exe)


def _request(**overrides: object) -> ModelRequest:
    system_text = TextPart(text="You are a chess analyst.")
    user_text = TextPart(text="Decide a move on ROOT.")
    messages = [
        Message(role=MessageRole.SYSTEM, parts=(system_text,)),
        Message(role=MessageRole.USER, parts=(user_text,)),
    ]
    tools = (
        ToolDefinition(name="board_expand", description="Expand a node", parameters={}),
        ToolDefinition(name="board_finalize", description="Commit a move", parameters={}),
    )
    fields: dict[str, object] = {
        "model": ModelRef(backend="provider.codex_cli", provider="codex-cli", model="gpt-5.6-luna"),
        "messages": messages,
        "tools": tools,
    }
    fields.update(overrides)
    return ModelRequest(**fields)  # type: ignore[arg-type]


def _context() -> CallContext:
    return CallContext(run_id="run_test", attempt_id="att_1")


async def _infer(backend: CodexCliBackend, request: ModelRequest | None = None):
    return await backend.infer(request or _request(), _context())


async def test_flattens_prompt_with_tool_protocol(tmp_path: Path) -> None:
    args_file = tmp_path / "args.txt"
    exe = _write_fake_codex(
        tmp_path, f"printf '%s\\n' \"$@\" > \"{args_file}\"\ncat <<'JSONL'\n{CANNED_EVENTS}JSONL\n"
    )
    backend = CodexCliBackend(executable=exe, reasoning_effort="high")
    await _infer(backend)
    recorded = args_file.read_text(encoding="utf-8")
    assert "[SYSTEM INSTRUCTION]" in recorded
    assert "Decide a move on ROOT." in recorded
    assert "[AVAILABLE TOOLS]" in recorded
    assert "board_finalize" in recorded
    assert "model_reasoning_effort=high" in recorded
    assert "-m" in recorded and "gpt-5.6-luna" in recorded


async def test_parses_agent_message_usage_and_tool_calls(tmp_path: Path) -> None:
    exe = _write_fake_codex(tmp_path, f"cat <<'JSONL'\n{CANNED_EVENTS}JSONL\n")
    backend = CodexCliBackend(executable=exe)
    result = await _infer(backend)
    assert "board_expand" in result.response.text()
    assert result.response.tool_calls[0].tool_name == "board_expand"
    assert result.response.tool_calls[0].arguments["node_id"] == "ROOT"
    assert result.response.usage.input_tokens == 150  # 100 fresh + 50 cached
    assert result.response.usage.output_tokens == 10
    telemetry = result.reasoning_telemetry
    assert telemetry is not None
    assert telemetry.reasoning_tokens == 4
    assert telemetry.availability.reasoning_tokens is True
    # the non-fatal codex error item surfaces as a warning, never fails the call
    assert any("Skill descriptions" in w for w in result.response.warnings)


async def test_timeout_maps_to_provider_timeout(tmp_path: Path) -> None:
    exe = _write_fake_codex(tmp_path, "sleep 5\n")
    backend = CodexCliBackend(executable=exe, timeout_seconds=0.3)
    with pytest.raises(ProviderTimeoutError):
        await _infer(backend)


async def test_nonzero_exit_maps_to_provider_response_error(tmp_path: Path) -> None:
    exe = _write_fake_codex(tmp_path, "echo 'stream error' >&2\nexit 3\n")
    backend = CodexCliBackend(executable=exe)
    with pytest.raises(ProviderResponseError, match="code 3"):
        await _infer(backend)


async def test_missing_agent_message_maps_to_provider_response_error(tmp_path: Path) -> None:
    events = '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":0}}\n'
    exe = _write_fake_codex(tmp_path, f"cat <<'JSONL'\n{events}JSONL\n")
    backend = CodexCliBackend(executable=exe)
    with pytest.raises(ProviderResponseError, match="no agent message"):
        await _infer(backend)


async def test_missing_binary_maps_to_provider_connection_error(tmp_path: Path) -> None:
    backend = CodexCliBackend(executable=str(tmp_path / "does-not-exist"))
    with pytest.raises(ProviderConnectionError):
        await _infer(backend)


async def test_max_output_tokens_is_forwarded(tmp_path: Path) -> None:
    args_file = tmp_path / "args2.txt"
    exe = _write_fake_codex(
        tmp_path, f"printf '%s\\n' \"$@\" > \"{args_file}\"\ncat <<'JSONL'\n{CANNED_EVENTS}JSONL\n"
    )
    backend = CodexCliBackend(executable=exe, max_output_tokens=32768)
    await _infer(backend)
    assert "model_max_output_tokens=32768" in args_file.read_text(encoding="utf-8")


def test_descriptor_declares_capabilities() -> None:
    backend = CodexCliBackend(executable="/unused")
    caps = backend.descriptor.default_capabilities
    assert Capability.TEXT_INPUT in caps
    assert Capability.TOOL_CALLING in caps
    assert Capability.REASONING_CONTROL in caps
    assert Capability.USAGE_REPORTING in caps


async def test_inspect_capabilities_missing_required_raises() -> None:
    backend = CodexCliBackend(executable="/unused")
    with pytest.raises(CapabilityMissingError):
        await backend.inspect_capabilities(
            ModelRef(backend="provider.codex_cli", provider="codex-cli", model="gpt-5.6-luna"),
            required=frozenset({Capability.STREAMING}),
        )


def test_wire_request_omits_prompt_body(tmp_path: Path) -> None:
    """Attribution keeps the invocation skeleton, never the full prompt body."""
    exe = _write_fake_codex(tmp_path, f"cat <<'JSONL'\n{CANNED_EVENTS}JSONL\n")
    backend = CodexCliBackend(executable=exe)
    result = json.loads(json.dumps(_run_infer(backend)))
    assert result["wire_request"]["prompt_length"] > 0
    assert all(part != "You are a chess analyst." for part in result["wire_request"]["cmd"])


def _run_infer(backend: CodexCliBackend) -> dict[str, object]:
    import asyncio

    result = asyncio.run(backend.infer(_request(), _context()))
    return {
        "wire_request": result.wire_request,
        "prompt": None,
    }
