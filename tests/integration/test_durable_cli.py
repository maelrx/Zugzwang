"""CLI integration for durable runs (SQLite + CAS)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zugzwang_cli.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "experiments/fake-smoke.yaml"


@pytest.mark.integration
class TestDurableCli:
    def test_run_list_show_db_roundtrip(self, tmp_path) -> None:
        ws = str(tmp_path / "ws")
        assert runner.invoke(app, ["init", ws]).exit_code == 0
        run_result = runner.invoke(app, ["run", MANIFEST, "--workspace", ws, "--output", "json"])
        assert run_result.exit_code == 0, run_result.output
        payload = json.loads(run_result.output)
        assert payload["status"] == "COMPLETED"
        run_id = payload["run_id"]

        list_result = runner.invoke(app, ["runs", "list", "--workspace", ws, "--output", "json"])
        assert list_result.exit_code == 0
        runs = json.loads(list_result.output)
        assert any(r["run_id"] == run_id for r in runs)

        show_result = runner.invoke(
            app, ["runs", "show", run_id, "--workspace", ws, "--output", "json"]
        )
        assert show_result.exit_code == 0
        summary = json.loads(show_result.output)
        assert summary["status"] == "COMPLETED"
        assert summary["steps_committed"] == 6

        db_result = runner.invoke(app, ["db", "status", "--workspace", ws, "--output", "json"])
        assert db_result.exit_code == 0
        status = json.loads(db_result.output)
        assert status["tables_exist"] is True

    def test_run_requires_workspace(self, tmp_path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "zugzwang_cli.main", "run", str(REPO_ROOT / MANIFEST)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        assert result.returncode != 0
        assert "workspace" in result.stderr.lower()

    def test_resume_missing_run_exits_cleanly(self, tmp_path) -> None:
        ws = str(tmp_path / "ws")
        assert runner.invoke(app, ["init", ws]).exit_code == 0
        result = runner.invoke(
            app, ["resume", "run_nonexistent1234567890", MANIFEST, "--workspace", ws]
        )
        assert result.exit_code != 0
