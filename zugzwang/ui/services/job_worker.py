from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from zugzwang.infra.ids import timestamp_utc


def _extract_last_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    candidate = text.strip()
    if not candidate:
        return None

    for index in range(len(candidate) - 1, -1, -1):
        if candidate[index] != "{":
            continue
        try:
            payload, end = decoder.raw_decode(candidate[index:])
        except json.JSONDecodeError:
            continue

        trailing = candidate[index + end :].strip()
        if trailing:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _write_status(
    exit_code_path: Path,
    command: list[str],
    exit_code: int,
    started_at_utc: str,
    payload: dict[str, Any] | None,
    error: str | None = None,
) -> None:
    exit_code_path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "command": command,
        "exit_code": int(exit_code),
        "started_at_utc": started_at_utc,
        "finished_at_utc": timestamp_utc(),
        "payload": payload,
        "error": error,
    }
    exit_code_path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def _run_child(
    command: list[str],
    stdout_path: Path,
    stderr_path: Path,
    workdir: Path,
) -> tuple[int, dict[str, Any] | None, str | None]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    with stdout_path.open("a", encoding="utf-8") as out_fp, stderr_path.open(
        "a", encoding="utf-8"
    ) as err_fp:
        try:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                stdout=out_fp,
                stderr=err_fp,
                text=True,
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            return 1, None, str(exc)
        exit_code = process.wait()

    payload = _extract_last_json_object(stdout_path.read_text(encoding="utf-8", errors="replace"))
    return exit_code, payload, None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="zugzwang-ui-job-worker")
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    parser.add_argument("--exit-code-path", required=True)
    parser.add_argument("--workdir", default=".")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing command to execute")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    command = [str(part) for part in args.command]
    stdout_path = Path(args.stdout_path)
    stderr_path = Path(args.stderr_path)
    exit_code_path = Path(args.exit_code_path)
    workdir = Path(args.workdir)

    started_at_utc = timestamp_utc()
    exit_code, payload, error = _run_child(command, stdout_path, stderr_path, workdir)
    _write_status(
        exit_code_path=exit_code_path,
        command=command,
        exit_code=exit_code,
        started_at_utc=started_at_utc,
        payload=payload,
        error=error,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
