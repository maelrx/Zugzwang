"""CLI tests: behavior via CliRunner, exit codes via subprocess."""

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


def run_module(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "zugzwang_cli.main", *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        check=False,
    )


@pytest.mark.unit
class TestCli:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "doctor" in result.output

    def test_plugins_list_json(self) -> None:
        result = runner.invoke(app, ["plugins", "list", "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        plugin_ids = {p["plugin_id"] for p in payload["plugins"]}
        assert "fake.backend" in plugin_ids
        assert "provider.openai_compatible" in plugin_ids

    def test_validate(self) -> None:
        result = runner.invoke(app, ["experiment", "validate", MANIFEST])
        assert result.exit_code == 0
        assert "valid: True" in result.output

    def test_plan(self) -> None:
        result = runner.invoke(app, ["experiment", "plan", MANIFEST, "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["total_estimated_calls"] == 12

    def test_run_fake(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("ZUGZWANG_WAL_POLICY", "ephemeral")
        result = runner.invoke(
            app,
            ["run", MANIFEST, "--workspace", str(tmp_path), "--output", "json"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "COMPLETED"
        assert payload["output_dir"]

    def test_schema_export(self, tmp_path) -> None:
        result = runner.invoke(app, ["schema", "--out", str(tmp_path), "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload["schemas"]) == 7

    def test_init_and_doctor(self, tmp_path) -> None:
        init_result = runner.invoke(app, ["init", str(tmp_path / "ws"), "--output", "json"])
        assert init_result.exit_code == 0
        doctor_result = runner.invoke(
            app, ["doctor", "--directory", str(tmp_path / "ws"), "--output", "json"]
        )
        # The sqlite check is honest about the locally linked SQLite (TEST-081):
        # on machines without an approved corrected line the doctor reports
        # status "error" and exits with a configuration error.
        from zugzwang_runtime.persistence.sqlite_policy import admitted, effective_version

        payload = json.loads(doctor_result.output)
        if admitted(effective_version()):
            assert doctor_result.exit_code == 0
            assert payload["status"] in {"ok", "warn"}
        else:
            assert doctor_result.exit_code != 0
            assert payload["status"] == "error"

    def test_patch_flag(self) -> None:
        result = runner.invoke(
            app,
            [
                "experiment",
                "plan",
                MANIFEST,
                "--set",
                "/spec/budget/max_calls=3",
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["conditions"][0]["budget_ceiling"]["max_calls"] == 3

    def test_deterministic_plan(self) -> None:
        first = runner.invoke(app, ["experiment", "plan", MANIFEST, "--output", "json"])
        second = runner.invoke(app, ["experiment", "plan", MANIFEST, "--output", "json"])
        assert json.loads(first.output) == json.loads(second.output)


@pytest.mark.unit
class TestCliExitCodes:
    def test_validate_bad_manifest_exit_2(self, tmp_path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "api_version: zgw.dev/v1alpha1\nkind: Experiment\nmetadata: {name: 'x'}\n",
            encoding="utf-8",
        )
        result = run_module(["experiment", "validate", str(bad)])
        assert result.returncode == 2, result.stderr
        assert "spec" in result.stderr

    def test_missing_manifest_exit_2(self) -> None:
        result = run_module(["experiment", "validate", "does-not-exist.yaml"])
        assert result.returncode == 2

    def test_unknown_plugin_exit_6(self, tmp_path) -> None:
        bad = tmp_path / "bad-plugin.yaml"
        bad.write_text(
            """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata: {name: 'bad-plugin'}
spec:
  seed: 1
  task: {plugin: 'no.such.plugin', config: {episodes: 1}}
  players:
    white: {model: {backend: 'fake.backend', provider: 'fake', model: 'scripted', strategy: 'fake.direct'}}
    black: {policy: {plugin: 'fake.stay'}}
  protocol: {declared_assistance: H2, declared_knowledge: K0}
  budget: {max_calls: 1}
  evaluation: []
  artifacts: {redact: standard}
""",
            encoding="utf-8",
        )
        result = run_module(["experiment", "plan", str(bad)])
        assert result.returncode == 6, result.stderr
        assert "not installed" in result.stderr

    def test_success_exit_0(self) -> None:
        result = run_module(["experiment", "validate", MANIFEST])
        assert result.returncode == 0
