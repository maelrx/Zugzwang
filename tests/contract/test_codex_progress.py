"""Public summary delivery must happen before infer finishes; offline executable."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from zgw_provider_codex_cli.adapter import CodexCliBackend
from zgw_provider_codex_cli.progress import public_summary

from tests.contract.test_codex_cli_adapter import (
    CANNED_EVENTS,
    _context,
    _request,
    _write_fake_codex,
)
from zugzwang_core.domain.errors import ProviderTimeoutError


async def test_summary_arrives_before_completion_and_isolated_from_raw(tmp_path: Path) -> None:
    release = tmp_path / "release"
    summary = json.dumps(
        {
            "type": "item.completed",
            "item": {"id": "s1", "type": "reasoning", "text": "Checking candidate safety."},
        }
    )
    raw = json.dumps(
        {"type": "item.completed", "item": {"id": "r1", "type": "raw_reasoning", "text": "PRIVATE"}}
    )
    exe = _write_fake_codex(
        tmp_path,
        f"cat <<'JSONL'\n{raw}\n{summary}\n{summary}\nJSONL\nwhile [ ! -f '{release}' ]; do sleep 0.02; done\ncat <<'JSONL'\n{CANNED_EVENTS}JSONL\n",
    )
    backend = CodexCliBackend(executable=exe)
    received = asyncio.Event()
    rows = []

    def observe(row):
        rows.append(row)
        received.set()

    task = asyncio.create_task(backend.infer_with_progress(_request(), _context(), observe))
    try:
        await asyncio.wait_for(received.wait(), 3)
        assert not task.done(), "Summary was buffered until completion"
        assert rows == [{"id": "s1", "text": "Checking candidate safety.", "source": "codex-cli"}]
    finally:
        release.touch()
    result = await task
    assert result.response.tool_calls[0].tool_name == "board_expand"
    assert "PRIVATE" in json.dumps(result.wire_response)  # raw evidence not rewritten
    # The normal path after opt-in must not retain the callback.
    await backend.infer(_request(), _context())
    assert len(rows) == 1


async def test_progress_callback_failure_does_not_change_inference(tmp_path: Path) -> None:
    event = '{"type":"item.completed","item":{"id":"s1","type":"reasoning","text":"Summary"}}'
    exe = _write_fake_codex(tmp_path, f"cat <<'JSONL'\n{event}\n{CANNED_EVENTS}JSONL\n")

    def broken(_):
        raise RuntimeError("UI unavailable")

    result = await CodexCliBackend(executable=exe).infer_with_progress(
        _request(), _context(), broken
    )
    assert result.response.tool_calls


async def test_stream_timeout_remains_ambiguous_and_does_not_retry(tmp_path: Path) -> None:
    exe = _write_fake_codex(tmp_path, "exec sleep 20\n")
    with pytest.raises(ProviderTimeoutError):
        await CodexCliBackend(executable=exe, timeout_seconds=0.05).infer_with_progress(
            _request(), _context(), lambda _: None
        )


def test_only_public_summary_event_is_accepted() -> None:
    for kind in ["agent_message", "raw_reasoning", "command_execution", "reasoning_content"]:
        assert (
            public_summary(
                {"type": "item.completed", "item": {"type": kind, "text": "do not display"}}
            )
            is None
        )
    assert public_summary({"type": "reasoning.delta", "text": "do not display"}) is None


async def test_long_json_lines_and_no_final_newline(tmp_path: Path) -> None:
    event = json.dumps(
        {"type": "item.completed", "item": {"id": "long", "type": "reasoning", "text": "x" * 80000}}
    )
    exe = _write_fake_codex(
        tmp_path, f"cat <<'JSONL'\n{event}\n{CANNED_EVENTS}JSONL\nprintf '%s' '{event}'\n"
    )
    rows = []
    result = await CodexCliBackend(executable=exe).infer_with_progress(
        _request(), _context(), rows.append
    )
    assert len(rows) == 1
    assert len(rows[0]["text"]) == 80000
    assert result.response.tool_calls
