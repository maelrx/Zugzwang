from __future__ import annotations

from zugzwang.strategy.prompts import DEFAULT_PROMPT_ID, prompt_registry, resolve_system_prompt


def test_prompt_registry_contains_required_prompt_variants() -> None:
    registry = prompt_registry()
    required = {
        DEFAULT_PROMPT_ID,
        "bare_minimum",
        "grandmaster_persona",
        "structured_analysis",
        "checklist_strict",
        "self_critique",
    }
    assert required.issubset(set(registry))


def test_resolve_system_prompt_interpolates_known_variables() -> None:
    resolved = resolve_system_prompt(
        system_prompt_id="structured_analysis",
        variables={"color": "white", "phase": "opening"},
        custom_template=None,
    )

    assert resolved.effective_id == "structured_analysis"
    assert resolved.fallback_applied is False
    assert "white" in resolved.rendered_template
    assert "opening" in resolved.rendered_template


def test_resolve_system_prompt_falls_back_to_default_for_unknown_id() -> None:
    resolved = resolve_system_prompt(
        system_prompt_id="unknown_prompt_id",
        variables={"color": "black", "phase": "middlegame"},
        custom_template=None,
    )

    assert resolved.effective_id == DEFAULT_PROMPT_ID
    assert resolved.fallback_applied is True
    assert "chess assistant" in resolved.rendered_template
