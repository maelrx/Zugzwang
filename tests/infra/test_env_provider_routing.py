from __future__ import annotations

from zugzwang.infra.env import validate_provider_secrets


def test_validate_provider_secrets_accepts_kimi_25_with_kimicode_key() -> None:
    config = {
        "players": {
            "white": {"type": "random", "name": "random_white"},
            "black": {
                "type": "llm",
                "name": "llm_black",
                "provider": "kimi",
                "model": "kimi-2.5",
            },
        }
    }
    validate_provider_secrets(
        config,
        env={
            "KIMI_CODE_API_KEY": "test-kimi-code-key",
        },
    )
