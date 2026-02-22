from __future__ import annotations

import json
import os
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zugzwang.providers.base import ProviderError, ProviderResponse


class AnthropicProvider:
    """Provider adapter for Anthropic Messages-compatible APIs."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        default_model: str = "claude-opus-4-1-20250805",
        provider_label: str = "Anthropic",
        base_url_env: str = "ANTHROPIC_BASE_URL",
        timeout_env: str = "ANTHROPIC_TIMEOUT_SECONDS",
    ) -> None:
        self.api_key_env = api_key_env
        self.default_model = default_model
        self.provider_label = provider_label
        self.base_url = (
            base_url
            or os.environ.get(base_url_env)
            or "https://api.anthropic.com/v1"
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

        model = str(model_config.get("model") or os.environ.get("ANTHROPIC_MODEL", self.default_model)).strip()
        anthropic_messages, system_prompt = _convert_messages(messages)
        max_tokens = int(model_config.get("max_tokens", os.environ.get("ANTHROPIC_MAX_TOKENS", 1024)) or 1024)
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        for field in ("temperature", "top_p"):
            if field in model_config:
                payload[field] = model_config[field]

        req = Request(
            url=_messages_url(self.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
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

        content = data.get("content", [])
        if not isinstance(content, list):
            raise ProviderError(
                f"{self.provider_label} response missing content: {data}",
                category="invalid_response",
                retryable=False,
            )

        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
        text = "\n".join(part for part in chunks if part).strip()

        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)

        return ProviderResponse(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )


def _convert_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], str | None]:
    anthropic_messages: list[dict[str, str]] = []
    system_parts: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user")).strip().lower()
        content = str(item.get("content", ""))
        if role == "system":
            if content:
                system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        anthropic_messages.append({"role": role, "content": content})
    if not anthropic_messages:
        anthropic_messages = [{"role": "user", "content": ""}]
    system_prompt = "\n".join(part for part in system_parts if part).strip()
    return anthropic_messages, system_prompt or None


def _messages_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    if normalized.endswith("/anthropic"):
        return f"{normalized}/v1/messages"
    return f"{normalized}/messages"


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
