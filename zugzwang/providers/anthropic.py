from __future__ import annotations

from typing import Any

from zugzwang.providers.base import ProviderError, ProviderResponse


class AnthropicProvider:
    """Placeholder adapter for future Anthropic integration."""

    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        raise ProviderError(
            "Anthropic provider not wired yet. Use provider=mock for local runs.",
            category="unsupported_provider",
            retryable=False,
        )
