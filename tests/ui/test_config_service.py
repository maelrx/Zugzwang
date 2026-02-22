from __future__ import annotations

from pathlib import Path

from zugzwang.ui.services.config_service import ConfigService


ROOT = Path(__file__).resolve().parents[2]


def test_parse_overrides_ignores_comments_and_blank_lines() -> None:
    raw = "\n# comment\nruntime.max_plies=20\nexperiment.target_valid_games=1\n"
    parsed = ConfigService.parse_overrides(raw)
    assert parsed == ["runtime.max_plies=20", "experiment.target_valid_games=1"]


def test_validate_config_from_baseline_is_ok() -> None:
    service = ConfigService(config_root=ROOT / "configs")
    validation = service.validate_config(
        config_path=ROOT / "configs" / "baselines" / "best_known_start.yaml",
        overrides=["experiment.target_valid_games=1"],
    )
    assert validation.ok is True
    assert validation.config_hash is not None


def test_resolve_preview_includes_run_metadata() -> None:
    service = ConfigService(config_root=ROOT / "configs")
    preview = service.resolve_config_preview(
        config_path=ROOT / "configs" / "baselines" / "best_known_start.yaml",
        overrides=["experiment.target_valid_games=1", "runtime.max_plies=8"],
    )
    assert preview.run_id.startswith("best_known_start-")
    assert preview.scheduled_games >= 1
    assert len(preview.config_hash) == 64
