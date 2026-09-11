"""Arena opencode-go provider: deepseek-v4.1-flash via the local router."""

from __future__ import annotations

from typing import Any

import pytest
from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

from zugzwang_cli.arena.providers import REGISTRY, _deepseek_factory


def test_catalog_exposes_deepseek_v41_flash() -> None:
    entry = REGISTRY["opencode-go"]
    catalog = entry.catalog()
    assert catalog["available"] is True
    assert catalog["backend_id"] == "provider.openai_compatible"
    assert catalog["default_effort"] == "low"
    assert catalog["efforts"] == ["low", "high", "max"]
    model_ids = [m["id"] for m in catalog["models"]]
    assert "deepseek-v4.1-flash" in model_ids


def test_factory_builds_responses_backend_with_low_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(OpenAiCompatibleBackend, "__init__", fake_init)
    _deepseek_factory(model="deepseek-v4.1-flash", reasoning_effort="low", timeout_seconds=180)
    assert captured["base_url"] == "http://127.0.0.1:8788/v1"
    assert captured["profile"] == "openai-responses"
    assert captured["reasoning_effort"] == "low"
    assert captured["allow_private_network"] is True


def test_factory_defaults_to_low_when_effort_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(OpenAiCompatibleBackend, "__init__", fake_init)
    _deepseek_factory(model="deepseek-v4.1-flash")
    assert captured["reasoning_effort"] == "low"
