from __future__ import annotations

from zugzwang.providers.openai import OpenAIProvider


class GrokProvider(OpenAIProvider):
    """xAI Grok adapter via OpenAI-compatible chat completions."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(
            base_url=base_url or "https://api.x.ai/v1",
            timeout_seconds=timeout_seconds,
            api_key_env="XAI_API_KEY",
            default_model="grok-4",
            provider_label="xAI Grok",
            base_url_env="XAI_BASE_URL",
            timeout_env="XAI_TIMEOUT_SECONDS",
        )
