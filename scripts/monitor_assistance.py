#!/usr/bin/env python3
"""Assistance monitor for antigravity/agy runs (ZGW-0123).

Watches, every 15s:
- engine processes (stockfish/uci) spawned outside the kernel;
- provider isolation violations persisted in the canonical DB;
- tool calls recorded in the raw stream evidence of active runs.
Writes an audit line to /tmp/zgw-assist-monitor.log and exits on demand.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sqlite3
import subprocess
import time

REPO = pathlib.Path("/home/maelrx/Documents/ChatGPT/Zugzwang")
DB = REPO / ".zugzwang" / "state.db"
LOG = pathlib.Path("/tmp/zgw-assist-monitor.log")
RISKY = {
    "run_command",
    "read_url_content",
    "search_web",
    "open_browser_url",
    "execute_browser_javascript",
    "call_mcp_tool",
    "invoke_subagent",
    "write_to_file",
}


def log(message: str) -> None:
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")


def active_runs() -> list[str]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT run_id FROM runs WHERE status='RUNNING' AND run_id IN (
              SELECT DISTINCT e.run_id FROM steps s
              JOIN episodes e ON s.episode_id = e.episode_id
              WHERE s.actor_id LIKE 'provider.antigravity%')
            """
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def violations() -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return int(
            conn.execute(
                "SELECT count(*) FROM attempts WHERE failure_code='ZGZ-SECURITY-001'"
            ).fetchone()[0]
        )
    finally:
        conn.close()


def latest_tools(run_id: str) -> list[str]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        refs = [
            row[0]
            for row in conn.execute(
                """
                SELECT a.wire_response_artifact_id FROM attempts a
                WHERE a.step_id LIKE 'dec-stp_%' AND a.wire_response_artifact_id IS NOT NULL
                ORDER BY a.rowid DESC LIMIT 24
                """
            ).fetchall()
            if row[0]
        ]
    finally:
        conn.close()
    tools: list[str] = []
    for ref in refs:
        hexd = str(ref).split(":", 1)[1]
        path = REPO / ".zugzwang" / "objects" / hexd[:2] / hexd[2:]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "step_update" not in text and "gemini-3.8" not in text:
            continue
        for name in RISKY:
            if f'"tool_name": "{name}"' in text or f'"tool_name":"{name}"' in text:
                tools.append(name)
    return sorted(set(tools))


def engine_processes() -> list[str]:
    result = subprocess.run(
        ["pgrep", "-af", "stockfish|/bin/stockfish|uci"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        line
        for line in result.stdout.splitlines()
        if "stockfish" in line and "pgrep" not in line and "monitor" not in line
    ]


def main() -> None:
    log("monitor start (antigravity/agy)")
    seen_violations = 0
    while True:
        try:
            runs = active_runs()
            count = violations()
            if count != seen_violations:
                log(f"ALERT isolation violations total={count} runs={runs}")
                seen_violations = count
            engines = engine_processes()
            if engines:
                log("ALERT engine processes: " + " | ".join(engines[:3]))
            for run_id in runs:
                tools = latest_tools(run_id)
                if tools:
                    log(f"ALERT risky tool calls run={run_id} tools={tools}")
            if runs:
                log(f"ok runs={len(runs)} violations={count}")
            time.sleep(15)
        except Exception as exc:  # keep the monitor alive
            log(f"monitor error: {type(exc).__name__}: {exc}")
            time.sleep(15)


if __name__ == "__main__":
    main()
