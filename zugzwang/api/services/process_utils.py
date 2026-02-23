from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
from pathlib import Path


def python_executable() -> str:
    return sys.executable


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return False
        payload = proc.stdout.strip()
        if not payload:
            return False
        rows = csv.reader(io.StringIO(payload))
        for row in rows:
            if len(row) < 2:
                continue
            raw_pid = row[1].strip()
            if raw_pid.isdigit() and int(raw_pid) == pid:
                return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0
    try:
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def tail_text(path: str | Path, max_chars: int = 4000) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]

