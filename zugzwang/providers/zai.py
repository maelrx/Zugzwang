from __future__ import annotations

import json
import os
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zugzwang.providers.base import ProviderError, ProviderResponse
from zugzwang.providers.pricing import estimate_zai_cost_usd, pricing_mode_from_env


class ZAIProvider:
    """Provider adapter for z.ai OpenAI-compatible chat completions API."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (
            base_url
            or os.environ.get("ZAI_BASE_URL")
            or "https://api.z.ai/api/coding/paas/v4"
        ).rstrip("/")
        self.pricing_mode = pricing_mode_from_env()
        env_timeout = os.environ.get("ZAI_TIMEOUT_SECONDS")
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        elif env_timeout:
            self.timeout_seconds = float(env_timeout)
        else:
            self.timeout_seconds = 120.0

    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        api_key = str(model_config.get("api_key") or os.environ.get("ZAI_API_KEY", "")).strip()
        if not api_key:
            raise ProviderError(
                "Missing ZAI_API_KEY for provider=zai",
                category="auth",
                retryable=False,
            )

        model = str(model_config.get("model") or os.environ.get("ZAI_MODEL", "glm-5"))
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
                f"z.ai HTTP {exc.code}: {detail}",
                category=category,
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise ProviderError(
                f"z.ai network error: {exc.reason}",
                category="network",
                retryable=True,
            ) from exc
        except TimeoutError as exc:
            raise ProviderError("z.ai request timeout", category="timeout", retryable=True) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "z.ai returned non-JSON response",
                category="invalid_response",
                retryable=False,
            ) from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(
                f"z.ai response missing choices: {data}",
                category="invalid_response",
                retryable=False,
            )

        message = choices[0].get("message", {})
        text = self._extract_message_text(message)
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        prompt_details = usage.get("prompt_tokens_details", {})
        cached_prompt_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
        pricing_mode = str(model_config.get("pricing_mode", self.pricing_mode)).strip().lower()
        cost_usd = estimate_zai_cost_usd(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            mode=pricing_mode,
        )

        return ProviderResponse(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )

    @staticmethod
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
