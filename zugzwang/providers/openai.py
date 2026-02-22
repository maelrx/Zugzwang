from __future__ import annotations

from typing import Any

from zugzwang.providers.base import ProviderError, ProviderResponse


class OpenAIProvider:
    """Placeholder adapter for future OpenAI integration."""

    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        raise ProviderError(
            "OpenAI provider not wired yet. Use provider=mock for local runs.",
            category="unsupported_provider",
            retryable=False,
        )
