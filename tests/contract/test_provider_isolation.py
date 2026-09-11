"""No provider-native execution; model proposals remain inert data."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from zgw_provider_codex_cli.adapter import CodexCliBackend
from zgw_provider_codex_cli.isolation import model_only_args

from tests.contract.test_codex_cli_adapter import _context, _request, _write_fake_codex
from zugzwang_core.domain.provider_isolation import (
    NATIVE_EXECUTION_TYPES,
    ProviderIsolationError,
    reject_native_execution,
)


@pytest.mark.parametrize("kind", sorted(NATIVE_EXECUTION_TYPES))
def test_every_declared_native_type_is_rejected(kind):
    wire = {"output": [{"type": kind, "output": "bestmove e2e4"}]}
    with pytest.raises(ProviderIsolationError) as raised:
        reject_native_execution(wire)
    assert raised.value.wire_response is wire
    assert raised.value.retryability.value == "none"


@pytest.mark.parametrize(
    "kind",
    [
        "exec_command_begin",
        "exec_command_end",
        "custom_tool_call",
        "dynamic_tool_call_request",
        "dynamic_tool_call_response",
        "hook_started",
        "hook_completed",
        "patch_apply_begin",
        "patch_apply_end",
        "unified_exec_startup",
        "unified_exec_interaction",
    ],
)
def test_legacy_codex_execution_events_are_rejected_at_top_level(kind):
    # Codex CLI serializes these outside the item.* envelope; a denylist that
    # only covers the envelope shape silently lets them through.
    with pytest.raises(ProviderIsolationError):
        reject_native_execution({"type": kind, "command": "stockfish", "output": "bestmove e2e4"})


@pytest.mark.parametrize(
    "wire",
    [
        {"type": "message", "content": [{"type": "text", "text": "e4"}]},
        {"object": "chat.completion", "choices": [{"message": {"content": "e4"}}]},
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
        {"type": "error", "message": "rate limited"},
    ],
)
def test_inert_provider_envelopes_are_not_rejected(wire):
    reject_native_execution(wire)


def test_normal_proposals_and_reasoning_keywords_are_not_execution():
    reject_native_execution(
        {
            "output": [
                {"type": "function_call", "name": "board_expand", "arguments": {"type": "tool"}},
                {"type": "reasoning", "text": "Do not execute Stockfish"},
            ]
        }
    )


@pytest.mark.parametrize(
    "wire",
    [
        {"object": "response", "output": [{"type": "new_remote_executor"}]},
        {"type": "item.completed", "item": {"type": "new_native_executor"}},
    ],
)
def test_unknown_native_types_fail_closed(wire):
    with pytest.raises(ProviderIsolationError):
        reject_native_execution(wire)


async def test_codex_unknown_stream_event_fails_closed(tmp_path: Path):
    events = [
        {"type": "brand_new_executor", "output": "bestmove e2e4"},
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"command":"board_finalize","arguments":{"node_id":"n0","action_id":"e2e4"}}',
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]
    exe = _write_fake_codex(
        tmp_path,
        "cat <<'JSONL'\n" + "\n".join(json.dumps(event) for event in events) + "\nJSONL\n",
    )
    backend = CodexCliBackend(executable=exe)
    with pytest.raises(ProviderIsolationError):
        await backend.infer(_request(), _context())


async def test_codex_blocks_engine_receipt_before_final_move(tmp_path: Path):
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "stockfish",
                "exit_code": 0,
                "aggregated_output": "bestmove e2e4",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"command":"board_finalize","arguments":{"node_id":"n0","action_id":"e2e4"}}',
            },
        },
    ]
    exe = _write_fake_codex(
        tmp_path, "cat <<'JSONL'\n" + "\n".join(json.dumps(x) for x in events) + "\nJSONL\n"
    )
    with pytest.raises(ProviderIsolationError) as raised:
        await CodexCliBackend(executable=exe).infer(_request(), _context())
    assert "command_execution" in json.dumps(raised.value.wire_response)


async def test_codex_profile_cannot_inherit_tools(tmp_path: Path):
    from tests.contract.test_codex_cli_adapter import CANNED_EVENTS

    args = tmp_path / "args"
    exe = _write_fake_codex(
        tmp_path, f'printf "%s\\n" "$@" > "{args}"\ncat <<\'JSONL\'\n{CANNED_EVENTS}JSONL\n'
    )
    await CodexCliBackend(executable=exe, service_tier="fast").infer(_request(), _context())
    actual = args.read_text().splitlines()
    for value in model_only_args():
        assert value in actual
    assert "service_tier=fast" in actual


async def test_antigravity_never_spawns_without_verified_tool_isolation(monkeypatch):
    from zgw_provider_antigravity_cli.adapter import AntigravityCliBackend

    async def forbidden(*a, **k):
        raise AssertionError("unsafe process was started")

    monkeypatch.setattr("asyncio.create_subprocess_exec", forbidden)
    with pytest.raises(ProviderIsolationError, match="blocked"):
        await AntigravityCliBackend().infer(_request(), _context())


async def test_opencode_requires_confirmed_deny_all_before_prompt():
    from zgw_provider_opencode.adapter import OpenCodeBackend

    requests = []

    def handle(r):
        requests.append(r)
        if r.url.path == "/session":
            return httpx.Response(200, json={"id": "untrusted", "permission": []})
        return httpx.Response(200, json={})

    backend = OpenCodeBackend(transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderIsolationError, match="deny-all"):
        await backend.infer(_request(), _context())
    assert json.loads(requests[0].content)["permission"] == [
        {"permission": "*", "pattern": "*", "action": "deny"}
    ]
    assert not any(r.url.path.endswith("/message") for r in requests)
    await backend.close()


@pytest.mark.parametrize("provider", ["openai", "zcode", "experiential"])
async def test_http_native_execution_never_normalizes(provider):
    from zgw_provider_experiential_labs.adapter import ExperientialLabsBackend
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend
    from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

    body = {
        "object": "response",
        "output": [{"type": "code_interpreter_call", "code": "stockfish"}],
    }
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    cls = {
        "openai": OpenAiCompatibleBackend,
        "zcode": ZCodeGlmBackend,
        "experiential": ExperientialLabsBackend,
    }[provider]
    backend = cls(base_url="http://mock.local/v1", transport=transport)
    with pytest.raises(ProviderIsolationError):
        await backend.infer(_request(), _context())
    await backend.close()


async def test_recording_backend_keeps_rejected_receipt_and_does_not_retry(tmp_path):
    from tests.integration.test_zgw0103_run_pin import _context as ctx
    from tests.integration.test_zgw0103_run_pin import _recording_backend, _scripted

    inner = _scripted({"tool": "board_finalize", "arguments": {"action_id": "e2e4"}})

    class ViolatingBackend:
        calls = 0

        async def infer(self, request, context):
            self.calls += 1
            result = await inner.infer(request, context)
            return result.model_copy(
                update={"wire_response": {"type": "command_execution", "command": "stockfish"}}
            )

    violating = ViolatingBackend()
    recorder = _recording_backend(tmp_path, violating, max_transport_retries=4)
    with pytest.raises(ProviderIsolationError):
        await recorder.infer(_request(), ctx("isolated"))
    with pytest.raises(ProviderIsolationError):
        await recorder.infer(_request(), ctx("retry"))
    with pytest.raises(ProviderIsolationError):
        recorder.assert_isolated()
    assert violating.calls == 1
    evidence = recorder.evidence_for_calls()["isolated"]
    assert evidence["wire_response_artifact_ref"]
    assert any(
        b"command_execution" in p.read_bytes() for p in (tmp_path / "cas").rglob("*") if p.is_file()
    )


async def test_codex_forwards_declared_schema_as_inert_response_constraint(tmp_path):
    from tests.contract.test_codex_cli_adapter import CANNED_EVENTS
    from zugzwang_core.ports.model import Capability, OutputConstraint

    captured = tmp_path / "schema.json"
    exe = _write_fake_codex(
        tmp_path,
        'while [ "$#" -gt 0 ]; do if [ "$1" = "--output-schema" ]; then shift; cp "$1" "'
        + str(captured)
        + "\"; fi; shift; done\ncat <<'JSONL'\n"
        + CANNED_EVENTS
        + "JSONL\n",
    )
    schema = {
        "type": "object",
        "properties": {"move": {"type": "string"}},
        "required": ["move"],
        "additionalProperties": False,
    }
    request = _request().model_copy(
        update={
            "output_constraint": OutputConstraint.model_validate(
                {"format": "json_schema", "schema": schema}
            ),
            "required_capabilities": frozenset({Capability.JSON_SCHEMA_OUTPUT}),
        }
    )
    backend = CodexCliBackend(executable=exe)
    assert (
        await backend.inspect_capabilities(request.model, required=request.required_capabilities)
    ).satisfied
    await backend.infer(request, _context())
    assert json.loads(captured.read_text()) == schema
