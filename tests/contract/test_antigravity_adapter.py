"""Antigravity CLI (agy) adapter contract: model-only with tool-call enforcement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from zgw_provider_antigravity_cli.adapter import AntigravityCliBackend

from zugzwang_core.domain.errors import ProviderTimeoutError
from zugzwang_core.domain.provider_isolation import ProviderIsolationError
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    OutputConstraint,
    TextPart,
    ToolCallPart,
    ToolDefinition,
)


def _write_fake_agy(tmp_path: Path, events: list[dict[str, object]]) -> str:
    exe = tmp_path / "fake-agy"
    body = "\n".join(json.dumps(event) for event in events)
    exe.write_text("#!/usr/bin/env bash\ncat <<'JSONL'\n" + body + "\nJSONL\n", encoding="utf-8")
    exe.chmod(0o755)
    return str(exe)


def _request() -> ModelRequest:
    return ModelRequest(
        model=ModelRef(
            backend="provider.antigravity_cli",
            provider="antigravity-cli",
            model="gemini-3.8-flash-low",
        ),
        messages=(
            Message(role=MessageRole.SYSTEM, parts=(TextPart(text="You decide the move."),)),
            Message(role=MessageRole.USER, parts=(TextPart(text="Decide on ROOT."),)),
        ),
        tools=(
            ToolDefinition(
                name="board_finalize",
                description="Finalize the move.",
                parameters={"type": "object"},
            ),
        ),
    )


def _context() -> CallContext:
    return CallContext(run_id="run_test")


def _answer_event(text: str) -> dict[str, object]:
    return {
        "event": "step_update",
        "step_update": {
            "step_index": 1,
            "state": "ACTIVE",
            "step_type": "agent_response",
            "text_delta": text,
        },
    }


def _result_event(input_tokens: int = 10, output_tokens: int = 4) -> dict[str, object]:
    return {
        "event": "result",
        "result": {
            "status": "SUCCESS",
            "response": "",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        },
    }


async def test_parses_finalize_proposal_and_usage(tmp_path: Path) -> None:
    exe = _write_fake_agy(
        tmp_path,
        [
            {"event": "init", "init": {"model": "gemini-3.8-flash-low", "tools": ["run_command"]}},
            _answer_event(
                '```json\n{"command": "board_finalize", "arguments": '
                '{"node_id": "n0", "action_id": "e2e4"}}\n```'
            ),
            _result_event(input_tokens=12, output_tokens=7),
        ],
    )
    backend = AntigravityCliBackend(executable=exe)
    result = await backend.infer(_request(), _context())
    calls = result.response.tool_calls
    assert len(calls) == 1
    assert isinstance(calls[0], ToolCallPart)
    assert calls[0].tool_name == "board_finalize"
    assert calls[0].arguments == {"node_id": "n0", "action_id": "e2e4"}
    assert result.response.usage.input_tokens == 12
    assert result.response.usage.output_tokens == 7
    assert result.wire_response is not None
    assert result.wire_response["events"]
    await backend.close()


@pytest.mark.parametrize("tool_name", ["run_command", "read_url_content", "search_web"])
async def test_risky_tool_calls_abort_with_isolation_error(tmp_path: Path, tool_name: str) -> None:
    exe = _write_fake_agy(
        tmp_path,
        [
            {
                "event": "step_update",
                "step_update": {
                    "step_index": 2,
                    "state": "ACTIVE",
                    "step_type": "tool",
                    "tool_name": tool_name,
                    "tool_input": {"command": "stockfish"},
                },
            },
            _result_event(),
        ],
    )
    backend = AntigravityCliBackend(executable=exe)
    with pytest.raises(ProviderIsolationError) as raised:
        await backend.infer(_request(), _context())
    wire = raised.value.wire_response
    assert wire is not None
    assert tool_name in json.dumps(wire)
    await backend.close()


async def test_timeout_maps_to_provider_timeout(tmp_path: Path) -> None:
    exe = _write_fake_agy(tmp_path, [_answer_event("thinking...")])
    slow = tmp_path / "slow-agy"
    slow.write_text("#!/usr/bin/env bash\n" + exe + "\nsleep 30\n", encoding="utf-8")
    slow.chmod(0o755)
    backend = AntigravityCliBackend(executable=str(slow), timeout_seconds=1.0)
    with pytest.raises(ProviderTimeoutError):
        await backend.infer(_request(), _context())
    await backend.close()


async def test_flatten_includes_tools_and_system(tmp_path: Path) -> None:
    captured: dict[str, str] = {}
    exe = tmp_path / "capture-agy"
    exe.write_text(
        "#!/usr/bin/env bash\nprintf '%s' \"$2\" > " + str(tmp_path / "prompt.txt") + "\n"
        "cat <<'JSONL'\n" + json.dumps(_result_event()) + "\nJSONL\n",
        encoding="utf-8",
    )
    exe.chmod(0o755)
    backend = AntigravityCliBackend(executable=str(exe))
    await backend.infer(_request(), _context())
    prompt = (tmp_path / "prompt.txt").read_text(encoding="utf-8")
    captured["prompt"] = prompt
    assert "[SYSTEM INSTRUCTION]" in prompt
    assert "board_finalize" in prompt
    assert "[AVAILABLE TOOLS]" in prompt
    await backend.close()


async def test_json_schema_constraint_is_forwarded_to_agy(tmp_path: Path) -> None:
    args_file = tmp_path / "args.txt"
    exe = tmp_path / "args-agy"
    exe.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > " + str(args_file) + "\n"
        "cat <<'JSONL'\n" + json.dumps(_result_event()) + "\nJSONL\n",
        encoding="utf-8",
    )
    exe.chmod(0o755)
    request = _request().model_copy(
        update={
            "output_constraint": OutputConstraint(
                format="json_schema",
                schema={"type": "object", "properties": {"node_id": {"type": "string"}}},
            )
        }
    )
    backend = AntigravityCliBackend(executable=str(exe))
    await backend.infer(request, _context())
    args = args_file.read_text(encoding="utf-8").splitlines()
    assert "--json-schema" in args
    schema_payload = args[args.index("--json-schema") + 1]
    assert "node_id" in schema_payload
    await backend.close()
