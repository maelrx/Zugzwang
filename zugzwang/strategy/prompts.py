from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


DEFAULT_PROMPT_ID = "default"


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    label: str
    template: str
    notes: str = ""


@dataclass(frozen=True)
class PromptResolution:
    requested_id: str
    effective_id: str
    label: str
    rendered_template: str
    fallback_applied: bool


_PROMPT_REGISTRY: dict[str, PromptTemplate] = {
    "default": PromptTemplate(
        prompt_id="default",
        label="Default Assistant",
        template=(
            "You are a chess assistant playing one move.\n"
            "Return exactly one legal move in UCI format.\n"
            "Do not include explanation."
        ),
        notes="Default baseline template.",
    ),
    "bare_minimum": PromptTemplate(
        prompt_id="bare_minimum",
        label="Bare Minimum",
        template=(
            "You are playing chess as {color}.\n"
            "Return exactly one legal move in UCI format.\n"
            "Do not include explanation."
        ),
        notes="Control prompt with minimum instruction overhead.",
    ),
    "grandmaster_persona": PromptTemplate(
        prompt_id="grandmaster_persona",
        label="Grandmaster Persona",
        template=(
            "You are a chess grandmaster (2700+ Elo) playing as {color}.\n"
            "Before moving, quickly assess threats, opponent intent, and piece activity.\n"
            "Return exactly one legal move in UCI format. No explanation."
        ),
        notes="Persona framing for higher-level positional play.",
    ),
    "structured_analysis": PromptTemplate(
        prompt_id="structured_analysis",
        label="Structured Analysis",
        template=(
            "You are an expert chess player as {color}. Current phase: {phase}.\n"
            "Evaluate in order: tactics, material, piece activity, king safety.\n"
            "Choose the move that addresses the highest-priority factor.\n"
            "Return exactly one legal move in UCI format. No explanation."
        ),
        notes="Structured rubric for consistent move selection.",
    ),
    "checklist_strict": PromptTemplate(
        prompt_id="checklist_strict",
        label="Checklist Strict",
        template=(
            "You are a disciplined chess engine playing as {color}.\n"
            "Mandatory checks: opponent threat, tactical opportunity, hanging pieces, king safety.\n"
            "Return exactly one legal move in UCI format only."
        ),
        notes="Checklist-oriented prompt for instruction adherence.",
    ),
    "self_critique": PromptTemplate(
        prompt_id="self_critique",
        label="Self Critique",
        template=(
            "You are a strong chess player as {color}. Current phase: {phase}.\n"
            "Consider top candidate moves and reject weaker options before finalizing.\n"
            "Return only one legal move in UCI format. No explanation."
        ),
        notes="Internal candidate filtering prompt.",
    ),
}


def prompt_registry() -> dict[str, PromptTemplate]:
    return dict(_PROMPT_REGISTRY)


def resolve_system_prompt(
    *,
    system_prompt_id: str | None,
    variables: Mapping[str, str] | None = None,
    custom_template: str | None = None,
) -> PromptResolution:
    requested_id = (system_prompt_id or DEFAULT_PROMPT_ID).strip() or DEFAULT_PROMPT_ID

    inline_template = custom_template.strip() if isinstance(custom_template, str) else ""
    if inline_template:
        rendered = _safe_format(inline_template, variables or {})
        return PromptResolution(
            requested_id=requested_id,
            effective_id="inline_custom",
            label="Inline Custom",
            rendered_template=rendered,
            fallback_applied=False,
        )

    template = _PROMPT_REGISTRY.get(requested_id)
    fallback_applied = False
    if template is None:
        template = _PROMPT_REGISTRY[DEFAULT_PROMPT_ID]
        fallback_applied = True

    rendered = _safe_format(template.template, variables or {})
    return PromptResolution(
        requested_id=requested_id,
        effective_id=template.prompt_id,
        label=template.label,
        rendered_template=rendered,
        fallback_applied=fallback_applied,
    )


def _safe_format(template: str, variables: Mapping[str, str]) -> str:
    class _SafeDict(dict[str, str]):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            return "{" + key + "}"

    payload = _SafeDict({str(key): str(value) for key, value in variables.items()})
    return template.format_map(payload)
