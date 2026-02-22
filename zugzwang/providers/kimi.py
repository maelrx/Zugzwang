from __future__ import annotations

from zugzwang.providers.openai import OpenAIProvider


class KimiProvider(OpenAIProvider):
    """Moonshot Kimi adapter via OpenAI-compatible chat completions."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(
            base_url=base_url or "https://api.moonshot.cn/v1",
            timeout_seconds=timeout_seconds,
            api_key_env="MOONSHOT_API_KEY",
            default_model="kimi-k2-0905-preview",
            provider_label="Moonshot Kimi",
            base_url_env="MOONSHOT_BASE_URL",
            timeout_env="MOONSHOT_TIMEOUT_SECONDS",
        )
