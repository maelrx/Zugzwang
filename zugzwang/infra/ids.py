from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256


def short_hash(full_hash: str, length: int = 10) -> str:
    return full_hash[:length]


def make_run_id(experiment_name: str, config_hash_value: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{experiment_name}-{ts}-{short_hash(config_hash_value, 8)}"


def game_seed(base_seed: int, game_number: int) -> int:
    payload = f"{base_seed}:{game_number}".encode("utf-8")
    digest = sha256(payload).hexdigest()
    return int(digest[:8], 16)


def timestamp_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
