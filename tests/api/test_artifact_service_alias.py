from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.api.services.artifact_service import ArtifactService


def test_load_run_summary_resolves_alias_by_experiment_and_hash(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)

    actual_run_id = "qa_run_cancel_20260222143457-20260222T173541Z-e597406e"
    requested_run_id = "qa_run_cancel_20260222143457-20260222T173539Z-e597406e"
    (root / actual_run_id).mkdir(parents=True, exist_ok=True)

    service = ArtifactService(root=root)
    summary = service.load_run_summary(requested_run_id)

    assert summary.run_meta.run_id == actual_run_id
    assert summary.run_meta.run_dir == str(root / actual_run_id)
    assert summary.game_count == 0


def test_load_run_summary_raises_when_no_matching_alias(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir(parents=True, exist_ok=True)
    service = ArtifactService(root=root)

    with pytest.raises(FileNotFoundError):
        service.load_run_summary("missing_experiment-20260222T173539Z-deadbeef")
