"""Protocol-level prompt overrides (persona + few-shot) for chess strategies."""

from __future__ import annotations

from typing import Any, cast

from zugzwang_core.domain.prompt_program import PromptProgram
from zugzwang_core.ports.strategy import DecisionContext


def _override_from_config(context: DecisionContext) -> dict[str, Any] | None:
    raw = context.config.get("prompt")
    if not isinstance(raw, dict):
        return None
    return cast(dict[str, Any], raw)


def apply_prompt_override(program: PromptProgram, context: DecisionContext) -> PromptProgram:
    """Merge protocol.prompt into a PromptProgram (persona + examples)."""
    override = _override_from_config(context)
    if override is None:
        return program
    updates: dict[str, Any] = {}
    system_instructions = override.get("system_instructions")
    if isinstance(system_instructions, str) and system_instructions:
        updates["system_instructions"] = system_instructions
    examples_raw = override.get("examples")
    if isinstance(examples_raw, list):
        raw_list = cast(list[Any], examples_raw)
        cleaned: list[dict[str, str]] = []
        for raw_example in raw_list:
            if isinstance(raw_example, dict):
                cleaned.append(cast(dict[str, str], raw_example))
        if cleaned:
            updates["examples"] = tuple(cleaned)
    if not updates:
        return program
    return program.model_copy(update=updates)


def apply_prompt_override_text(prompt_text: str, context: DecisionContext) -> str:
    """Text-level override for strategies without a PromptProgram."""
    override = _override_from_config(context)
    if override is None:
        return prompt_text
    sections: list[str] = []
    system_instructions = override.get("system_instructions")
    if isinstance(system_instructions, str) and system_instructions:
        sections.append(system_instructions)
    sections.append(prompt_text)
    examples_raw = override.get("examples")
    if isinstance(examples_raw, list):
        raw_list = cast(list[Any], examples_raw)
        for raw_example in raw_list:
            if isinstance(raw_example, dict):
                example = cast(dict[str, str], raw_example)
                sections.append(f"Example {example.get('label', '')}:\n{example.get('text', '')}")
    return "\n\n".join(sections)


def append_retry_feedback(prompt_text: str, context: DecisionContext) -> str:
    """Add formal legality feedback when the runtime rejected a prior move."""
    feedback = context.config.get("retry_feedback")
    if isinstance(feedback, str) and feedback:
        return f"{prompt_text}\n\n{feedback}"
    return prompt_text
