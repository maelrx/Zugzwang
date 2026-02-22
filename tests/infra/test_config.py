from __future__ import annotations

from pathlib import Path

from zugzwang.infra.config import config_hash, deep_merge, resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


def test_deep_merge_is_deterministic() -> None:
    base = {"a": {"b": 1, "c": 2}, "x": 5}
    override = {"a": {"c": 9, "d": 10}, "y": True}
    merged = deep_merge(base, override)
    assert merged == {"a": {"b": 1, "c": 9, "d": 10}, "x": 5, "y": True}


def test_config_hash_is_order_independent() -> None:
    a = {"b": 1, "a": {"d": 2, "c": 3}}
    b = {"a": {"c": 3, "d": 2}, "b": 1}
    assert config_hash(a) == config_hash(b)


def test_resolve_with_hash_from_baseline() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved, cfg_hash = resolve_with_hash(config_path)
    assert resolved["protocol"]["mode"] == "direct"
    assert resolved["strategy"]["board_format"] == "fen"
    assert len(cfg_hash) == 64
