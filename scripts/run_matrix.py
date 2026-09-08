#!/usr/bin/env python3
"""ZGW-0103 P0.5 — campaign runner with a GLOBAL concurrency cap.

Operator directive (2026-09-08): at most FIVE partidas running simultaneously.
This script is the campaign scheduler: it queues experiment manifests and
keeps at most --max-concurrent `zugzwang run` processes alive, each pinned to
its own workspace directory. Provider throttling inside a run is handled by
the runtime (Retry-After honored, ZGW-0103 R5); this layer only bounds how
many games share the route/quota at once.

Usage:
    python scripts/run_matrix.py experiments/cb2-*.yaml --max-concurrent 5 \
        --workspace-root /tmp/cb2-campaign

Offline by construction: it launches the same CLI the operator uses; every
network/budget decision stays inside the manifest and the runtime.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_MAX_CONCURRENT = 5


@dataclass
class GameOutcome:
    manifest: Path
    workspace: Path
    returncode: int | None
    started_at: str
    finished_at: str
    elapsed_s: float
    log_path: Path
    run_id: str | None = None
    status: str = "unknown"
    notes: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _experiment_name(manifest: Path) -> str:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    return manifest.stem


def run_one(manifest: Path, workspace: Path, repo_root: Path, log_path: Path) -> GameOutcome:
    started = time.monotonic()
    started_at = _now_iso()
    workspace.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uv",
        "run",
        "zugzwang",
        "run",
        str(manifest),
        "--workspace",
        str(workspace),
        "--output",
        "json",
    ]
    outcome = GameOutcome(
        manifest=manifest,
        workspace=workspace,
        returncode=None,
        started_at=started_at,
        finished_at="",
        elapsed_s=0.0,
        log_path=log_path,
    )
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        log.flush()
        try:
            completed = subprocess.run(
                cmd,
                cwd=repo_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            outcome.returncode = completed.returncode
        except KeyboardInterrupt:
            outcome.returncode = None
            outcome.status = "interrupted"
            outcome.notes.append("runner interrupted; child left to the operator")
            return _finish(outcome, started)
    outcome.status = "ok" if outcome.returncode == 0 else f"exit_{outcome.returncode}"
    outcome.run_id = _last_run_id(workspace)
    return _finish(outcome, started)


def _finish(outcome: GameOutcome, started: float) -> GameOutcome:
    outcome.elapsed_s = round(time.monotonic() - started, 1)
    outcome.finished_at = _now_iso()
    return outcome


def _last_run_id(workspace: Path) -> str | None:
    import sqlite3

    db = workspace / "data" / "state.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return str(row[0]) if row else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path, help="experiment yaml files")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT,
        help=f"global cap of simultaneous games (operator directive; default {DEFAULT_MAX_CONCURRENT})",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        required=True,
        help="directory that receives one workspace per game",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="run logs directory (default: <workspace-root>/logs)",
    )
    args = parser.parse_args(argv)

    if args.max_concurrent < 1:
        parser.error("--max-concurrent must be >= 1")
    repo_root = Path(__file__).resolve().parent.parent
    manifests = [m.resolve() for m in args.manifests]
    for manifest in manifests:
        if not manifest.exists():
            parser.error(f"manifest not found: {manifest}")
    workspace_root = args.workspace_root.resolve()
    logs_dir = (args.logs_dir or (workspace_root / "logs")).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    print(
        f"[run_matrix] {len(manifests)} game(s), cap={args.max_concurrent}, root={workspace_root}",
        flush=True,
    )
    outcomes: list[GameOutcome] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.max_concurrent) as pool:
        futures = {}
        for manifest in manifests:
            name = _experiment_name(manifest)
            workspace = workspace_root / name
            log_path = logs_dir / f"{name}.log"
            futures[pool.submit(run_one, manifest, workspace, repo_root, log_path)] = name
        for future in as_completed(futures):
            outcome = future.result()
            outcomes.append(outcome)
            print(
                f"[run_matrix] {futures[future]}: {outcome.status} "
                f"({outcome.elapsed_s}s, run={outcome.run_id})",
                flush=True,
            )
    outcomes.sort(key=lambda o: o.started_at)
    summary = {
        "schema_version": "zgw.campaign-summary/v1",
        "max_concurrent": args.max_concurrent,
        "workspace_root": str(workspace_root),
        "wall_clock_s": round(time.monotonic() - started, 1),
        "games": [
            {
                "manifest": str(o.manifest),
                "workspace": str(o.workspace),
                "run_id": o.run_id,
                "status": o.status,
                "returncode": o.returncode,
                "elapsed_s": o.elapsed_s,
                "log": str(o.log_path),
                "started_at": o.started_at,
                "finished_at": o.finished_at,
            }
            for o in outcomes
        ],
    }
    summary_path = logs_dir / "campaign_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[run_matrix] summary: {summary_path}", flush=True)
    failed = [o for o in outcomes if o.returncode not in (0,)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
