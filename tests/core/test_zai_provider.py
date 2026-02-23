from __future__ import annotations

import json

from zugzwang.providers.zai import ZAIProvider


def test_zai_provider_defaults_thinking_disabled_and_fallbacks_to_reasoning(monkeypatch) -> None:
    monkeypatch.setenv("ZAI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            payload = {
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "e2e4",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(req, timeout=120):  # type: ignore[no-untyped-def]
        captured["timeout"] = timeout
        captured["request_payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("zugzwang.providers.zai.urlopen", fake_urlopen)

    provider = ZAIProvider(base_url="https://api.z.ai/api/coding/paas/v4", timeout_seconds=5)
    response = provider.complete(
        messages=[{"role": "user", "content": "Return one legal UCI move only."}],
        model_config={"model": "glm-5", "max_tokens": 16},
    )

    request_payload = captured["request_payload"]
    assert isinstance(request_payload, dict)
    assert request_payload.get("thinking") == {"type": "disabled"}
    assert response.text == "e2e4"
