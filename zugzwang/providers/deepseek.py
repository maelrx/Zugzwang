from __future__ import annotations

from zugzwang.providers.openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek adapter via OpenAI-compatible chat completions."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(
            base_url=base_url or "https://api.deepseek.com",
            timeout_seconds=timeout_seconds,
            api_key_env="DEEPSEEK_API_KEY",
            default_model="deepseek-chat",
            provider_label="DeepSeek",
            base_url_env="DEEPSEEK_BASE_URL",
            timeout_env="DEEPSEEK_TIMEOUT_SECONDS",
        )
