"""Opt-in observation of Codex's public reasoning-summary events.

The CLI's `reasoning` item is documented as ReasoningItem (summary).
Raw reasoning, messages, commands, tool arguments and stderr are never forwarded.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, cast

from zugzwang_core.domain.provider_isolation import reject_native_execution

from .isolation import reject_unknown_codex_event

SummarySink = Callable[[dict[str, Any]], None]
summary_sink: ContextVar[SummarySink | None] = ContextVar("codex_summary_sink", default=None)


def public_summary(event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("type") not in {"item.started", "item.updated", "item.completed"}:
        return None
    item = event.get("item")
    if not isinstance(item, dict):
        return None
    item = cast("dict[str, Any]", item)
    if item.get("type") != "reasoning":
        return None
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return {"id": str(item.get("id", "summary")), "text": text, "source": "codex-cli"}


async def read_with_summaries(
    child: asyncio.subprocess.Process, timeout: float, sink: SummarySink
) -> tuple[bytes, bytes]:
    assert child.stdout is not None and child.stderr is not None
    stdout: asyncio.StreamReader = child.stdout
    seen: dict[str, str] = {}

    def deliver(line: bytes) -> None:
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            return
        reject_native_execution(event)
        reject_unknown_codex_event(event)
        summary = public_summary(cast("dict[str, Any]", event)) if isinstance(event, dict) else None
        if summary and seen.get(summary["id"]) != summary["text"]:
            seen[summary["id"]] = summary["text"]
            # Observation cannot change a provider decision or cause a retry.
            with contextlib.suppress(Exception):
                sink(summary)

    async def read_stdout() -> bytes:
        chunks: list[bytes] = []
        pending = bytearray()
        # Chunked reads avoid StreamReader.readline's 64 KiB line limit.
        while True:
            chunk: bytes = await stdout.read(16384)
            if not chunk:
                break
            chunks.append(chunk)
            pending.extend(chunk)
            while (newline := pending.find(b"\n")) >= 0:
                deliver(bytes(pending[:newline]))
                del pending[: newline + 1]
        if pending:
            deliver(bytes(pending))
        return b"".join(chunks)

    readers = asyncio.gather(read_stdout(), child.stderr.read())
    try:
        async with asyncio.timeout(timeout):
            out, err = await readers
            await child.wait()
        return out, err
    finally:
        if child.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                child.kill()
            await child.wait()
        readers.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await readers
