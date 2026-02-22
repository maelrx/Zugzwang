from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class EnvironmentError(ValueError):
    """Raised when runtime environment requirements are not satisfied."""


PROVIDER_ENV_KEYS = {
    "zai": "ZAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "mock": None,
}


def load_dotenv(path: str | Path = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _llm_players(config: dict[str, Any]) -> list[dict[str, Any]]:
    players = config.get("players", {})
    selected: list[dict[str, Any]] = []
    for color in ("white", "black"):
        player = players.get(color)
        if isinstance(player, dict) and player.get("type") == "llm":
            selected.append(player)
    return selected


def validate_provider_secrets(config: dict[str, Any], env: dict[str, str] | None = None) -> None:
    environment = env or os.environ
    for player in _llm_players(config):
        provider = str(player.get("provider", "")).lower()
        if provider not in PROVIDER_ENV_KEYS:
            raise EnvironmentError(f"Unknown provider '{provider}'")
        key_name = PROVIDER_ENV_KEYS[provider]
        if not key_name:
            continue
        if not environment.get(key_name):
            raise EnvironmentError(
                f"Missing provider secret: {key_name} (provider={provider})"
            )


def validate_environment(config: dict[str, Any], dotenv_path: str | Path = ".env") -> None:
    load_dotenv(dotenv_path)
    validate_provider_secrets(config)
