from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def runs_root() -> Path:
    return project_root() / "results" / "runs"


def ui_jobs_root() -> Path:
    return project_root() / "results" / "ui_jobs"
