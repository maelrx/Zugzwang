"""Create the ten controlled MuseSpark-vs-Stockfish battery manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
OUTPUT_DIR = Path("experiments/musespark-stockfish-battery")

COMMON_OBSERVATION = {
    "position": {"fen": True, "ascii": False},
    "side_to_move": True,
    "move_number": True,
    "history": {"mode": "last_n", "plies": 6, "notation": "uci"},
}

VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "slug": "01-baseline-fen-uci",
        "label": "baseline FEN + UCI history",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": COMMON_OBSERVATION,
    },
    {
        "slug": "02-legal-grounding",
        "label": "legal action grounding",
        "strategy": "chess.grounded",
        "assistance": "H3",
        "observation": {
            **COMMON_OBSERVATION,
            "legal_actions": {"exposure": "always", "encoding": "uci"},
        },
    },
    {
        "slug": "03-reason-then-ground",
        "label": "reason then ground",
        "strategy": "chess.reason_then_ground",
        "assistance": "H3",
        "observation": {
            **COMMON_OBSERVATION,
            "legal_actions": {"exposure": "always", "encoding": "uci"},
        },
    },
    {
        "slug": "04-formal-repair",
        "label": "formal repair",
        "strategy": "chess.repair",
        "assistance": "H2",
        "observation": {
            **COMMON_OBSERVATION,
            "legal_actions": {"exposure": "always", "encoding": "uci"},
        },
    },
    {
        "slug": "05-structured-output",
        "label": "structured JSON output",
        "strategy": "chess.structured",
        "assistance": "H4",
        "observation": COMMON_OBSERVATION,
    },
    {
        "slug": "06-ascii-board",
        "label": "ASCII board representation",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": {
            **COMMON_OBSERVATION,
            "position": {"fen": False, "ascii": True},
        },
    },
    {
        "slug": "07-full-uci-history",
        "label": "full UCI history",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": {
            **COMMON_OBSERVATION,
            "history": {"mode": "full", "plies": 0, "notation": "uci"},
        },
    },
    {
        "slug": "08-full-san-history",
        "label": "full SAN history",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": {
            **COMMON_OBSERVATION,
            "history": {"mode": "full", "plies": 0, "notation": "san"},
        },
    },
    {
        "slug": "09-rgb-board",
        "label": "RGB board plus FEN",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": {
            **COMMON_OBSERVATION,
            "image": {"enabled": True, "orientation": "white", "coordinates": True},
        },
        "image_input": True,
    },
    {
        "slug": "10-tactical-checklist",
        "label": "tactical checklist prompt",
        "strategy": "chess.direct",
        "assistance": "H2",
        "observation": COMMON_OBSERVATION,
        "prompt": {
            "system_instructions": (
                "Play standard chess. Before answering, check the side to move, legal "
                "checks, captures, attacked pieces and immediate threats. Then choose "
                "one move that is legal in the supplied position. Reply with exactly "
                "one UCI move and no explanation."
            ),
            "examples": [
                {
                    "label": "formato",
                    "text": "A resposta deve ter apenas uma jogada, por exemplo: e2e4.",
                }
            ],
        },
    },
)


def build_manifest(variant: dict[str, Any], index: int) -> dict[str, Any]:
    name = f"local-musespark-1-3-free-stockfish-battery-{variant['slug']}"
    backend_config = {
        "base_url": "http://127.0.0.1:8788/v1",
        "provider_id": "opencode-router",
        "timeout_seconds": 120,
        "profile": "openai-responses",
        "allow_private_network": True,
        "reasoning_effort": "minimal",
        "default_max_output_tokens": 4096,
    }
    if variant.get("image_input"):
        backend_config["image_input"] = True

    protocol: dict[str, Any] = {
        "declared_assistance": variant["assistance"],
        "declared_knowledge": "K0",
        "observation": variant["observation"],
        "retries": {
            # The local free-model proxy can throttle a request transiently.
            # Retry that transport failure without changing the chess retry
            # contract: illegal moves still have their own bounded counter.
            "transport": 5,
            "parse": 0,
            "illegal": 3,
            "feedback": "legality_only",
        },
    }
    if variant.get("prompt"):
        protocol["prompt"] = variant["prompt"]

    return {
        "api_version": "zgw.dev/v1alpha1",
        "kind": "Experiment",
        "metadata": {
            "name": name,
            "tags": [
                "local",
                "free-provider",
                "stockfish-battery",
                "single-game",
                variant["slug"],
            ],
        },
        "spec": {
            "seed": 20261000 + index,
            "task": {
                "plugin": "chess.tasks",
                "version": "0.1",
                "config": {
                    "kind": "full-game",
                    "start_fen": START_FEN,
                    "model_color": "white",
                    "max_plies": None,
                    "backend_config": backend_config,
                },
            },
            "players": {
                "white": {
                    "model": {
                        "backend": "provider.openai_compatible",
                        "provider": "opencode-router",
                        "model": "muse-spark-1.3-contributor-free",
                        "strategy": variant["strategy"],
                    }
                },
                "black": {
                    "policy": {
                        "plugin": "chess.stockfish",
                        "config": {
                            "executable": "/home/maelrx/.local/bin/stockfish",
                            "elo": 1000,
                            "allow_approximate": True,
                            "limit": {"nodes": 20000},
                            "options": {"Threads": "1", "Hash": "16"},
                        },
                    }
                },
            },
            "protocol": protocol,
            "budget": {
                "max_calls": None,
                "max_concurrent_episodes": 1,
                "max_attempts": 1,
            },
            "evaluation": [],
            "artifacts": {
                "raw_requests": True,
                "raw_responses": True,
                "redact": "standard",
            },
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for index, variant in enumerate(VARIANTS, start=1):
        path = OUTPUT_DIR / f"{variant['slug']}.yaml"
        path.write_text(
            yaml.safe_dump(
                build_manifest(variant, index),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    print(f"created {len(VARIANTS)} manifests in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
