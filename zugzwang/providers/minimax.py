from __future__ import annotations

from zugzwang.providers.anthropic import AnthropicProvider


class MiniMaxProvider(AnthropicProvider):
    """MiniMax adapter via Anthropic Messages-compatible endpoint."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(
            base_url=base_url or "https://api.minimaxi.com/anthropic",
            timeout_seconds=timeout_seconds,
            api_key_env="MINIMAX_API_KEY",
            default_model="MiniMax-M2.5",
            provider_label="MiniMax",
            base_url_env="MINIMAX_BASE_URL",
            timeout_env="MINIMAX_TIMEOUT_SECONDS",
        )
