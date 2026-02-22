from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ProviderResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


class ProviderError(RuntimeError):
    """Raised for provider connectivity or response failures."""

    def __init__(
        self,
        message: str,
        *,
        category: str | None = None,
        retryable: bool | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.status_code = status_code


RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
NON_RETRYABLE_HTTP_STATUS = {400, 401, 403, 404, 405, 422}

RETRYABLE_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "rate limit",
    "too many requests",
    "temporarily unavailable",
    "service unavailable",
    "gateway timeout",
    "connection reset",
    "connection aborted",
    "network error",
)

NON_RETRYABLE_ERROR_MARKERS = (
    "missing",
    "invalid api key",
    "unauthorized",
    "forbidden",
    "invalid request",
    "bad request",
    "unsupported",
    "not wired yet",
    "unknown provider",
)


def should_retry_provider_error(error: ProviderError) -> bool:
    if error.retryable is not None:
        return bool(error.retryable)

    if error.status_code is not None:
        if error.status_code in RETRYABLE_HTTP_STATUS:
            return True
        if error.status_code in NON_RETRYABLE_HTTP_STATUS:
            return False

    message = str(error).lower()
    for marker in NON_RETRYABLE_ERROR_MARKERS:
        if marker in message:
            return False
    for marker in RETRYABLE_ERROR_MARKERS:
        if marker in message:
            return True

    # Keep current behavior for unknown failures: assume temporary and retry.
    return True


class ProviderInterface(Protocol):
    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        """Run one chat completion call."""
