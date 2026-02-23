from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("filename", "enabled", "eco", "lichess", "endgames"),
    [
        ("rag_off.yaml", False, True, True, True),
        ("rag_openings_only.yaml", True, True, False, False),
        ("rag_openings_tactics.yaml", True, True, True, False),
        ("rag_variants.yaml", True, True, True, True),
    ],
)
def test_rag_ablation_configs_resolve_expected_source_flags(
    filename: str,
    enabled: bool,
    eco: bool,
    lichess: bool,
    endgames: bool,
) -> None:
    config_path = ROOT / "configs" / "ablations" / filename
    resolved, cfg_hash = resolve_with_hash(config_path)

    rag = resolved["strategy"]["rag"]
    include_sources = rag["include_sources"]

    assert len(cfg_hash) == 64
    assert rag["enabled"] is enabled
    assert include_sources["eco"] is eco
    assert include_sources["lichess"] is lichess
    assert include_sources["endgames"] is endgames
