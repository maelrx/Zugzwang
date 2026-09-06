"""Compatibility tests: bundles written by older builds import cleanly (ADR-030)."""

from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang_runtime.application.bundles import ImportRunBundleService
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import ArtifactRepository
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "compatibility" / "fake-bundle-v1"


@pytest.mark.compatibility
class TestBundleFixtureImport:
    def test_v1_fixture_imports(self, tmp_path) -> None:
        ws = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
        ws.ensure_layout()
        services = DurableRunServices(ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=services.cas,
            artifacts=ArtifactRepository(services.database_engine),
        )
        result = importer.import_bundle(FIXTURE)
        assert result["run_id"] == "run_fixture1234567890123456"
        assert int(result["artifacts_imported"]) == 1

    def test_v1_fixture_tamper_rejected(self, tmp_path) -> None:
        import json
        import shutil

        copy = tmp_path / "tampered"
        shutil.copytree(FIXTURE, copy)
        bundle = json.loads((copy / "bundle.json").read_text(encoding="utf-8"))
        bundle["schema_version"] = "zgw.bundle/v999"
        (copy / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
        ws = Workspace.from_root(tmp_path / "ws2", wal_policy="ephemeral")
        ws.ensure_layout()
        services = DurableRunServices(ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=services.cas,
            artifacts=ArtifactRepository(services.database_engine),
        )
        from zugzwang_core.domain.errors import SecurityError

        with pytest.raises(SecurityError):
            importer.import_bundle(copy)
