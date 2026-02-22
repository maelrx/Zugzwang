from __future__ import annotations

import json
import os
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zugzwang.providers.base import ProviderError, ProviderResponse


class OpenAIProvider:
    """Provider adapter for OpenAI-compatible chat completions APIs."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        default_model: str = "gpt-5-mini",
        provider_label: str = "OpenAI",
        base_url_env: str = "OPENAI_BASE_URL",
        timeout_env: str = "OPENAI_TIMEOUT_SECONDS",
    ) -> None:
        self.api_key_env = api_key_env
        self.default_model = default_model
        self.provider_label = provider_label
        self.base_url = (
            base_url
            or os.environ.get(base_url_env)
            or "https://api.openai.com/v1"
        ).rstrip("/")
        env_timeout = os.environ.get(timeout_env)
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        elif env_timeout:
            self.timeout_seconds = float(env_timeout)
        else:
            self.timeout_seconds = 120.0

    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        api_key = str(model_config.get("api_key") or os.environ.get(self.api_key_env, "")).strip()
        if not api_key:
            raise ProviderError(
                f"Missing {self.api_key_env} for provider={self.provider_label.lower()}",
                category="auth",
                retryable=False,
            )

        model = str(model_config.get("model") or os.environ.get("OPENAI_MODEL", self.default_model)).strip()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        for field in ("temperature", "top_p", "max_tokens"):
            if field in model_config:
                payload[field] = model_config[field]

        req = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        started = perf_counter()
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            category, retryable = _classify_http_status(exc.code)
            raise ProviderError(
                f"{self.provider_label} HTTP {exc.code}: {detail}",
                category=category,
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise ProviderError(
                f"{self.provider_label} network error: {exc.reason}",
                category="network",
                retryable=True,
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(
                f"{self.provider_label} request timeout",
                category="timeout",
                retryable=True,
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"{self.provider_label} returned non-JSON response",
                category="invalid_response",
                retryable=False,
            ) from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(
                f"{self.provider_label} response missing choices: {data}",
                category="invalid_response",
                retryable=False,
            )
        message = choices[0].get("message", {})
        text = _extract_message_text(message)

        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)

        return ProviderResponse(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )


def _extract_message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            else:
                chunks.append(str(item))
        return "\n".join(part for part in chunks if part).strip()
    return str(content)


def _classify_http_status(status_code: int) -> tuple[str, bool]:
    if status_code in {400, 404, 405, 422}:
        return "invalid_request", False
    if status_code in {401, 403}:
        return "auth", False
    if status_code == 429:
        return "rate_limit", True
    if status_code in {408, 409, 425, 500, 502, 503, 504}:
        return "server", True
    return "http_error", False
