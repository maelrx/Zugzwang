from __future__ import annotations

from typing import Any

from zugzwang.providers.anthropic import AnthropicProvider
from zugzwang.providers.base import ProviderError, ProviderInterface
from zugzwang.providers.deepseek import DeepSeekProvider
from zugzwang.providers.google import GoogleProvider
from zugzwang.providers.grok import GrokProvider
from zugzwang.providers.kimi import KimiProvider
from zugzwang.providers.kimicode import KimiCodeProvider
from zugzwang.providers.minimax import MiniMaxProvider
from zugzwang.providers.mock import MockProvider
from zugzwang.providers.openai import OpenAIProvider
from zugzwang.providers.zai import ZAIProvider


_PROVIDERS: dict[str, type[ProviderInterface]] = {
    "mock": MockProvider,
    "zai": ZAIProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "deepseek": DeepSeekProvider,
    "grok": GrokProvider,
    "kimi": KimiProvider,
    "kimicode": KimiCodeProvider,
    "minimax": MiniMaxProvider,
}


def create_provider(name: str, provider_config: dict[str, Any] | None = None) -> ProviderInterface:
    key = (name or "").lower()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ProviderError(
            f"Unknown provider '{name}'. Supported: {supported}",
            category="unknown_provider",
            retryable=False,
        )
    provider_config = provider_config or {}
    return provider_cls(**provider_config)
