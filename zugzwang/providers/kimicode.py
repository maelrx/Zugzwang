from __future__ import annotations

import os

from zugzwang.providers.anthropic import AnthropicProvider


class KimiCodeProvider(AnthropicProvider):
    """Kimi Code adapter via Anthropic Messages-compatible endpoint."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        # Allow existing aliases when a dedicated key is not configured.
        key = os.environ.get("KIMI_CODE_API_KEY", "").strip()
        if not key:
            key = os.environ.get("KIMI_API_KEY", "").strip()
        if not key:
            key = os.environ.get("MOONSHOT_API_KEY", "").strip()
        if key and not os.environ.get("KIMI_CODE_API_KEY", "").strip():
            os.environ["KIMI_CODE_API_KEY"] = key

        super().__init__(
            base_url=base_url or "https://api.kimi.com/coding/v1",
            timeout_seconds=timeout_seconds,
            api_key_env="KIMI_CODE_API_KEY",
            default_model="kimi-for-coding",
            provider_label="Kimi Code",
            base_url_env="KIMI_CODE_BASE_URL",
            timeout_env="KIMI_CODE_TIMEOUT_SECONDS",
        )
