"""Arena provider registry: the validated paths, exactly as runs build them.

Constructors mirror ``durable_services`` so arena calls ride the SAME adapter
configuration as campaign games. ``validated`` is an operator-maintained
empirical flag (ZGW-0108): only paths with real verified games carry it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

BackendFactory = Callable[..., Any]


class ProviderOption:
    def __init__(
        self,
        *,
        provider_id: str,
        backend_id: str,
        label: str,
        validated: bool,
        models: list[dict[str, Any]],
        default_effort: str | None,
        efforts: list[str] | None,
        factory: BackendFactory,
        note: str = "",
        available: bool = True,
        unavailable_reason: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.backend_id = backend_id
        self.label = label
        self.validated = validated
        self.models = models
        self.default_effort = default_effort
        self.efforts = efforts or []
        self.factory = factory
        self.note = note
        self.available = available
        self.unavailable_reason = unavailable_reason

    def catalog(self) -> dict[str, Any]:
        return {
            "id": self.provider_id,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "backend_id": self.backend_id,
            "label": self.label,
            "validated": self.validated,
            "models": self.models,
            "efforts": self.efforts,
            "default_effort": self.default_effort,
            "note": self.note,
        }


def _antigravity_factory(**config: Any) -> Any:
    from zgw_provider_antigravity_cli.adapter import AntigravityCliBackend

    return AntigravityCliBackend(
        model=str(config.get("model") or "gemini-3.8-flash-low"),
        executable=str(config["executable"]) if config.get("executable") else None,
        timeout_seconds=float(config.get("timeout_seconds") or 180),
        reasoning_effort=str(config["reasoning_effort"])
        if config.get("reasoning_effort")
        else None,
    )


def _opencode_factory(**config: Any) -> Any:
    from zgw_provider_opencode.adapter import OpenCodeBackend

    return OpenCodeBackend(
        base_url=str(config.get("base_url") or "http://127.0.0.1:8788"),
        provider_id=str(config.get("provider_id") or "opencode"),
        timeout_seconds=float(config.get("timeout_seconds") or 300),
        image_input=False,
    )


def _deepseek_factory(**config: Any) -> Any:
    """DeepSeek V4.1 Flash through the local opencode-go router (Responses)."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    return OpenAiCompatibleBackend(
        base_url=str(config.get("base_url") or "http://127.0.0.1:8788/v1"),
        profile=str(config.get("profile") or "openai-responses"),
        allow_private_network=True,
        timeout_seconds=float(config.get("timeout_seconds") or 300),
        reasoning_effort=(
            str(config["reasoning_effort"]) if config.get("reasoning_effort") else "low"
        ),
        default_max_output_tokens=int(config.get("default_max_output_tokens") or 8192),
    )


def _codex_factory(**config: Any) -> Any:
    from zgw_provider_codex_cli.adapter import CodexCliBackend

    return CodexCliBackend(
        model=str(config.get("model") or "gpt-6-astra"),
        service_tier=config.get("service_tier"),
        executable=str(config["executable"]) if config.get("executable") else None,
        timeout_seconds=float(config.get("timeout_seconds") or 300),
        reasoning_effort=str(config["reasoning_effort"])
        if config.get("reasoning_effort")
        else None,
    )


def _default_model(options: list[dict[str, Any]]) -> str:
    for option in options:
        if option.get("default"):
            return str(option["id"])
    return str(options[0]["id"])


REGISTRY: dict[str, ProviderOption] = {
    entry.provider_id: entry
    for entry in [
        ProviderOption(
            provider_id="antigravity-cli",
            backend_id="provider.antigravity_cli",
            label="Gemini (Antigravity CLI)",
            validated=True,
            models=[
                {
                    "id": "gemini-3.8-flash-low",
                    "label": "gemini-3.8-flash-low",
                    "validated": True,
                    "default": True,
                },
                {
                    "id": "gemini-3.8-flash-high",
                    "label": "gemini-3.8-flash-high",
                    "validated": False,
                    "default": False,
                },
            ],
            default_effort="low",
            efforts=["low", "medium", "high"],
            factory=_antigravity_factory,
            note="Melhor resultado empírico (parity com SF-1320 nos full games R1).",
            available=False,
            unavailable_reason="Bloqueado (ADR-063): o CLI não oferece isolamento de ferramentas verificável.",
        ),
        ProviderOption(
            provider_id="opencode",
            backend_id="provider.opencode",
            label="muse (opencode router)",
            validated=False,
            models=[
                {
                    "id": "muse-spark-1.3-contributor",
                    "label": "muse-spark-1.3-contributor",
                    "validated": False,
                    "default": True,
                },
            ],
            default_effort=None,
            efforts=[],
            factory=_opencode_factory,
            note="Exige o router opencode no ar (porta 8788) e header de sessão.",
        ),
        ProviderOption(
            provider_id="opencode-go",
            backend_id="provider.openai_compatible",
            label="DeepSeek V4.1 Flash (opencode-go)",
            validated=False,
            models=[
                {
                    "id": "deepseek-v4.1-flash",
                    "label": "deepseek-v4.1-flash",
                    "validated": False,
                    "default": True,
                },
            ],
            default_effort="low",
            efforts=["low", "high", "max"],
            factory=_deepseek_factory,
            note="Responses via router local 8788; thinking exige harness lowering (ZGW-0120).",
        ),
        ProviderOption(
            provider_id="codex-cli",
            backend_id="provider.codex_cli",
            label="Luna (Codex CLI)",
            validated=False,
            models=[
                {"id": "gpt-6-astra", "label": "gpt-6-astra", "validated": False, "default": True},
                {
                    "id": "gpt-5.6-luna",
                    "label": "gpt-5.6-luna",
                    "service_tiers": ["fast"],
                    "validated": False,
                    "default": False,
                },
            ],
            default_effort="high",
            efforts=["low", "medium", "high"],
            factory=_codex_factory,
            note="Trilha Luna/codex (ZGW-0105); single-flight próprio.",
        ),
    ]
}


def providers_catalog() -> list[dict[str, Any]]:
    return [entry.catalog() for entry in REGISTRY.values()]


def validate_service_tier(provider_id: str, model: str | None, tier: Any) -> str | None:
    if tier is None or tier == "":
        return None
    if tier != "fast" or provider_id != "codex-cli" or model != "gpt-5.6-luna":
        raise ValueError("O modo Fast está disponível apenas para o GPT-5.6 Luna.")
    return "fast"


def build_backend(
    provider_id: str,
    *,
    model: str | None,
    effort: str | None,
    timeout_seconds: float | None = None,
    service_tier: str | None = None,
) -> Any:
    option = REGISTRY.get(provider_id)
    if option is None:
        raise KeyError(f"unknown provider {provider_id!r}")
    tier = validate_service_tier(provider_id, model, service_tier)
    config: dict[str, Any] = {
        "model": model or _default_model(option.models),
        "reasoning_effort": effort or option.default_effort,
    }
    if tier:
        config["service_tier"] = tier
    if timeout_seconds:
        config["timeout_seconds"] = timeout_seconds
    return option.factory(**config)


__all__ = ["REGISTRY", "build_backend", "providers_catalog"]
