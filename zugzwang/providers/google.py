from __future__ import annotations

from zugzwang.providers.openai import OpenAIProvider


class GoogleProvider(OpenAIProvider):
    """Gemini adapter via Google's OpenAI-compatible endpoint."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta/openai",
            timeout_seconds=timeout_seconds,
            api_key_env="GEMINI_API_KEY",
            default_model="gemini-2.5-flash",
            provider_label="Google Gemini",
            base_url_env="GEMINI_BASE_URL",
            timeout_env="GEMINI_TIMEOUT_SECONDS",
        )
