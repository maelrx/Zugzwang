from __future__ import annotations

from pathlib import Path

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


def test_few_shot_calibration_config_enables_builtin_library() -> None:
    config_path = ROOT / "configs" / "ablations" / "few_shot_calibration.yaml"
    resolved, cfg_hash = resolve_with_hash(config_path)
    few_shot = resolved["strategy"]["few_shot"]

    assert len(cfg_hash) == 64
    assert few_shot["enabled"] is True
    assert few_shot["source"] == "builtin"
    assert few_shot["max_examples"] == 3
