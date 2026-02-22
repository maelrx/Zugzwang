from __future__ import annotations

import os

from fastapi import APIRouter

from zugzwang.api.schemas import EnvCheckResponse
from zugzwang.infra.env import PROVIDER_ENV_KEYS, load_dotenv


router = APIRouter(prefix="/env-check", tags=["env"])


@router.get("", response_model=list[EnvCheckResponse])
def env_check() -> list[EnvCheckResponse]:
    load_dotenv()
    checks: list[EnvCheckResponse] = []
    for provider, key_names in PROVIDER_ENV_KEYS.items():
        if key_names is None:
            checks.append(
                EnvCheckResponse(
                    provider=provider,
                    ok=True,
                    message="No secret required",
                )
            )
            continue

        present_key = next((key for key in key_names if os.environ.get(key, "").strip()), None)
        present = present_key is not None
        key_hint = " | ".join(key_names)
        checks.append(
            EnvCheckResponse(
                provider=provider,
                ok=present,
                message=f"{present_key or key_hint} {'set' if present else 'missing'}",
            )
        )

    stockfish_path = os.environ.get("STOCKFISH_PATH", "").strip()
    checks.append(
        EnvCheckResponse(
            provider="stockfish",
            ok=bool(stockfish_path),
            message="STOCKFISH_PATH set" if stockfish_path else "STOCKFISH_PATH missing",
        )
    )
    return checks

