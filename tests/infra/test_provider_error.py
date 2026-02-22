from __future__ import annotations

from zugzwang.providers.base import ProviderError, should_retry_provider_error


def test_should_retry_respects_explicit_flag() -> None:
    assert should_retry_provider_error(ProviderError("x", retryable=True)) is True
    assert should_retry_provider_error(ProviderError("x", retryable=False)) is False


def test_should_retry_by_http_status() -> None:
    assert should_retry_provider_error(ProviderError("rate limit", status_code=429)) is True
    assert should_retry_provider_error(ProviderError("unauthorized", status_code=401)) is False


def test_should_retry_by_message_heuristics() -> None:
    assert should_retry_provider_error(ProviderError("network error: connection reset")) is True
    assert should_retry_provider_error(ProviderError("provider not wired yet")) is False
