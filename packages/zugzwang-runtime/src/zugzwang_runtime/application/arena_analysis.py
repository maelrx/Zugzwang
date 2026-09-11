"""Persistent, single-worker post-game analysis. No chess or engine dependencies."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import re
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AnalysisEvaluator = Callable[[dict[str, Any], int], Iterator[dict[str, Any]]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ArenaAnalysisService:
    """Private application service; injected evaluators yield position results."""

    def __init__(
        self, directory: Path, evaluator: AnalysisEvaluator, profile: dict[str, Any]
    ) -> None:
        self.directory = directory
        self.evaluator = evaluator
        self.profile = profile
        self._lock = threading.RLock()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._jobs: dict[str, dict[str, Any]] = {}
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob("arena-*.json"):
            job = json.loads(path.read_text())
            self._jobs[job["game_id"]] = job
            if job["status"] in {"queued", "running"}:
                job["status"] = "interrupted"
                job["error"] = "Análise interrompida; retomando posições salvas."
        self._thread = threading.Thread(target=self._work, name="arena-analysis", daemon=True)
        self._thread.start()

    def get(self, game_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(game_id)
            if job is None:
                return {
                    "status": "not_started",
                    "depth": self.profile.get("depth", 20),
                    "positions": [],
                }
            return copy.deepcopy({k: v for k, v in job.items() if k != "source"})

    def enqueue(
        self, game_id: str, source: dict[str, Any], total: int, *, retry: bool = False
    ) -> dict[str, Any]:
        if not re.fullmatch(r"arena-[a-zA-Z0-9-]+", game_id):
            raise ValueError("Invalid arena game id")
        fingerprint = hashlib.sha256(
            json.dumps({"source": source, "profile": self.profile}, sort_keys=True).encode()
        ).hexdigest()
        with self._lock:
            job: dict[str, Any]
            old = self._jobs.get(game_id)
            if old and old["fingerprint"] == fingerprint:
                if old["status"] in {"queued", "running", "complete"}:
                    return self.get(game_id)
                if old["status"] == "failed" and not retry:
                    return self.get(game_id)
                job = old
            else:
                if old:
                    # Preserve prior generations if the source/profile changed.
                    archive = self.directory / f"{game_id}-{old['fingerprint'][:16]}.generation"
                    archive.write_text(json.dumps(old, ensure_ascii=False, indent=2))
                job = {
                    "schema": "zugzwang.arena-analysis/v1",
                    "game_id": game_id,
                    "fingerprint": fingerprint,
                    "source": copy.deepcopy(source),
                    "profile": copy.deepcopy(self.profile),
                    "depth": self.profile.get("depth", 20),
                    "total": total,
                    "positions": [],
                    "attempts": [],
                    "created_at": _now(),
                }
                self._jobs[game_id] = job
            job.update(status="queued", error=None, updated_at=_now())
            self._save(job)
            self._queue.put(game_id)
            return self.get(game_id)

    def _save(self, job: dict[str, Any]) -> None:
        path = self.directory / f"{job['game_id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2))
        os.replace(tmp, path)

    def _work(self) -> None:
        while (game_id := self._queue.get()) is not None:
            try:
                self._evaluate(game_id)
            finally:
                self._queue.task_done()

    def _evaluate(self, game_id: str) -> None:
        with self._lock:
            job = self._jobs[game_id]
            attempt = {"started_at": _now(), "status": "running"}
            job["attempts"].append(attempt)
            job.update(status="running", updated_at=_now())
            self._save(job)
            source = copy.deepcopy(job["source"])
            completed = len(job["positions"])
            log = (
                self.directory
                / f"{game_id}-{job['fingerprint'][:16]}-attempt-{len(job['attempts'])}.jsonl"
            )
        try:
            for position in self.evaluator(source, completed):
                with self._lock:
                    if position["ply"] != len(job["positions"]):
                        raise ValueError("Analysis returned an out-of-order position")
                    with log.open("a") as handle:
                        handle.write(json.dumps({"at": _now(), **position}) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    # Raw UCI evidence stays in the append-only attempt, not the UI payload.
                    job["positions"].append({k: v for k, v in position.items() if k != "raw_uci"})
                    job["updated_at"] = _now()
                    self._save(job)
            with self._lock:
                if len(job["positions"]) != job["total"]:
                    raise ValueError("Analysis ended without every position")
                job.update(status="complete", updated_at=_now(), error=None)
                attempt.update(status="complete", finished_at=_now())
                self._save(job)
        except Exception as exc:
            with self._lock:
                job.update(status="failed", updated_at=_now(), error=f"{type(exc).__name__}: {exc}")
                attempt.update(status="failed", finished_at=_now(), error=job["error"])
                self._save(job)

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)
