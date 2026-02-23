from __future__ import annotations

from pathlib import Path

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


PROMPT_CONFIGS = {
    "prompt_bare_minimum.yaml": "bare_minimum",
    "prompt_grandmaster_persona.yaml": "grandmaster_persona",
    "prompt_structured_analysis.yaml": "structured_analysis",
    "prompt_checklist_strict.yaml": "checklist_strict",
    "prompt_self_critique.yaml": "self_critique",
}


def test_prompt_ablation_configs_resolve_with_expected_prompt_ids() -> None:
    for filename, expected_prompt_id in PROMPT_CONFIGS.items():
        config_path = ROOT / "configs" / "ablations" / filename
        resolved, cfg_hash = resolve_with_hash(config_path)
        strategy = resolved["strategy"]

        assert len(cfg_hash) == 64
        assert strategy["use_system_prompt"] is True
        assert strategy["system_prompt_id"] == expected_prompt_id
        assert strategy["system_prompt_id_effective"] == expected_prompt_id
