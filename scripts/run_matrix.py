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
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_MAX_CONCURRENT = 5


def count_attempts(workspace_root: Path) -> int:
    """Total provider attempts across all run workspaces under the root."""
    total = 0
    for db in workspace_root.glob("*/.zugzwang/state.db"):
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                total += int(conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])
            finally:
                conn.close()
        except sqlite3.Error:
            continue
    return total


class CallLedger:
    """Campaign call-budget gate (ZGX wave 1: teto 1.400 calls).

    Checked before each launch against the CURRENT attempt rows on disk — a
    hard stop for the queue, never a silent overrun. Counting is conservative
    (attempts committed so far); a game already in flight is not interrupted.
    """

    def __init__(self, cap: int | None, workspace_root: Path) -> None:
        self.cap = cap
        self.workspace_root = workspace_root
        self.lock = threading.Lock()
        self.stopped = False

    def allow(self) -> bool:
        if self.cap is None:
            return True
        with self.lock:
            if self.stopped:
                return False
            if count_attempts(self.workspace_root) >= self.cap:
                self.stopped = True
                print(
                    f"[run_matrix] call ledger cap {self.cap} reached; no new launches",
                    flush=True,
                )
                return False
        return True


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


def run_one(
    manifest: Path,
    workspace: Path,
    repo_root: Path,
    log_path: Path,
    ledger: CallLedger | None = None,
) -> GameOutcome:
    started = time.monotonic()
    started_at = _now_iso()
    if ledger is not None and not ledger.allow():
        return GameOutcome(
            manifest=manifest,
            workspace=workspace,
            returncode=None,
            started_at=started_at,
            finished_at=_now_iso(),
            elapsed_s=0.0,
            log_path=log_path,
            status="skipped_call_budget",
            notes=["campaign call ledger cap reached before launch"],
        )
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
    db = workspace / ".zugzwang" / "state.db"
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
    parser.add_argument(
        "--max-total-attempts",
        type=int,
        default=None,
        help="campaign call ledger: no new game launches once total provider "
        "attempts under the root reach this cap (ZGX wave 1: 1400)",
    )
    parser.add_argument(
        "--single-flight",
        action="store_true",
        help="export ZGZ_MUSE_SINGLE_FLIGHT_LOCK to children: ONE Muse "
        "inference in flight across the whole shared quota (plano 28 §3.1)",
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
    ledger = CallLedger(args.max_total_attempts, workspace_root)
    if args.single_flight:
        lock_path = workspace_root / "muse.flight.lock"
        lock_path.touch(exist_ok=True)
        import os

        os.environ["ZGZ_MUSE_SINGLE_FLIGHT_LOCK"] = str(lock_path)
        print(f"[run_matrix] single-flight gate: {lock_path}", flush=True)
    with ThreadPoolExecutor(max_workers=args.max_concurrent) as pool:
        futures = {}
        for manifest in manifests:
            name = _experiment_name(manifest)
            workspace = workspace_root / name
            log_path = logs_dir / f"{name}.log"
            futures[pool.submit(run_one, manifest, workspace, repo_root, log_path, ledger)] = name
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
