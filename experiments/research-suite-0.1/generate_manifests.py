"""Generate the 14-condition research suite manifests from the frozen corpus.

Deterministic: same corpus + same script = same manifests. Emits a sha256
corpus manifest alongside the YAML files (ZGW-0076).

Blocks (per operator design):
  REP-001:   FEN, PGN, RGB, FEN+RGB
  GROUND-001: free (G0), legal-first (G2), reason-first (G4)
  SKILL-001: baseline, persona, correct, wrong, irrelevant
  MM-002:    consistent text+vision, single-piece conflict

Text model:  opencode-go/deepseek-v4-flash (subscription)
Vision model: opencode-go/gpt-5.6-luna (subscription, attachment=true)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

SUITE_DIR = Path(__file__).resolve().parent
CORPUS_PATH = SUITE_DIR.parent.parent / "datasets" / "positions_v1" / "positions.yaml"

TEXT_BACKEND = {
    "base_url": "http://127.0.0.1:4100",
    "provider_id": "opencode-go",
    "timeout_seconds": 300,
    "image_input": False,
}
VISION_BACKEND = {**TEXT_BACKEND, "image_input": True}


def conflict_fen(fen: str) -> str:
    """Deterministic one-piece conflict: displace one minor piece to an empty square."""
    board_part, *rest = fen.split(" ")
    rows = board_part.split("/")
    target = None
    for row_index, row in enumerate(rows):
        for col_index, char in enumerate(row):
            if char in "NnBb" and char not in "KkQqRrPp" and not char.isdigit():
                target = (row_index, col_index, char)
                break
        if target:
            break
    if target is None:
        raise ValueError(f"no minor piece to displace in {fen!r}")
    row_index, col_index, char = target
    rows[row_index] = rows[row_index][:col_index] + "1" + rows[row_index][col_index + 1 :]
    dest_row = rows[(row_index + 2) % 8]
    files = [c for c in dest_row if c.isdigit()]
    if not files:
        raise ValueError("no empty square found")
    file_index = 0
    dest_chars = list(dest_row)
    dest_chars[file_index] = str(int(dest_chars[file_index]) - 1) + char
    rows[(row_index + 2) % 8] = "".join(dest_chars)
    return "/".join(rows) + " " + " ".join(rest)


def manifest_block(block: str, extra: dict, *, vision: bool, knowledge_refs=(), declared_k=""):
    return {
        "block": block,
        "vision": vision,
        "extra": extra,
        "knowledge_refs": tuple(knowledge_refs),
        "declared_k": declared_k,
    }


def build_manifest(
    name: str,
    tags: list[str],
    positions: list[dict],
    model: dict,
    strategy: str,
    observation: dict,
    *,
    vision: bool = False,
    declared_assistance: str = "H2",
    declared_knowledge: str = "K0",
    knowledge_packets: tuple[str, ...] = (),
    prompt: dict | None = None,
    retries: dict | None = None,
) -> str:
    fens = [p["fen"] for p in positions]
    doc = {
        "api_version": "zgw.dev/v1alpha1",
        "kind": "Experiment",
        "metadata": {"name": name, "tags": tags},
        "spec": {
            "seed": 20260816,
            "matrix": {"mode": "zip", "parameters": {"start_fen": fens}},
            "task": {
                "plugin": "chess.tasks",
                "config": {
                    "kind": "move-selection",
                    "start_fen": "__matrix__",
                    "backend_config": TEXT_BACKEND if not vision else VISION_BACKEND,
                },
                "config_from_matrix": ["start_fen"],
            },
            "players": {
                "white": {"model": {**model, "strategy": strategy}},
                "black": {"policy": {"plugin": "fake.stay"}},
            },
            "protocol": {
                "declared_assistance": declared_assistance,
                "declared_knowledge": declared_knowledge,
                "observation": observation,
                "retries": retries or {"transport": 1, "parse": 0, "illegal": 0},
                "knowledge_packets": list(knowledge_packets),
                **({"prompt": prompt} if prompt else {}),
            },
            "budget": {"max_calls": 25, "max_concurrent_episodes": 1},
            "evaluation": [{"plugin": "evaluator.stockfish"}],
            "artifacts": {
                "raw_requests": True,
                "raw_responses": True,
                "redact": "standard",
            },
        },
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def main() -> None:
    corpus_raw = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))
    positions = corpus_raw["positions"]
    corpus_bytes = CORPUS_PATH.read_bytes()
    corpus_sha = hashlib.sha256(corpus_bytes).hexdigest()
    (SUITE_DIR / "corpus.sha256").write_text(f"{corpus_sha}  positions.yaml\n")

    text_model = {
        "backend": "provider.opencode",
        "provider": "opencode-go",
        "model": "deepseek-v4-flash",
    }
    vision_model = {
        "backend": "provider.opencode",
        "provider": "opencode-go",
        "model": "gpt-5.6-luna",
    }

    fen_obs = {
        "position": {"fen": True},
        "side_to_move": True,
        "move_number": True,
        "history": {"mode": "none"},
    }
    pgn_obs = {
        "position": {"fen": False},
        "side_to_move": True,
        "move_number": True,
        "history": {"mode": "full", "notation": "san"},
    }
    rgb_obs = {
        "position": {"fen": False},
        "side_to_move": False,
        "move_number": True,
        "history": {"mode": "none"},
        "image": {"enabled": True, "orientation": "white", "coordinates": True},
    }
    fen_rgb_obs = {
        "position": {"fen": True},
        "side_to_move": True,
        "move_number": True,
        "history": {"mode": "none"},
        "image": {"enabled": True, "orientation": "white", "coordinates": True},
    }
    grounded_obs = {**fen_obs, "legal_actions": {"exposure": "always", "encoding": "uci"}}
    reason_obs = {**fen_obs, "legal_actions": {"exposure": "delayed", "encoding": "uci"}}
    manifests: dict[str, str] = {}
    manifests["rep-001-fen.yaml"] = build_manifest(
        "rep-001-fen",
        ["e2e", "real-provider", "rep-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
    )
    manifests["rep-001-pgn.yaml"] = build_manifest(
        "rep-001-pgn",
        ["e2e", "real-provider", "rep-001"],
        positions,
        text_model,
        "chess.direct",
        pgn_obs,
    )
    manifests["rep-001-rgb.yaml"] = build_manifest(
        "rep-001-rgb",
        ["e2e", "real-provider", "rep-001", "multimodal"],
        positions,
        vision_model,
        "chess.direct",
        rgb_obs,
        vision=True,
    )
    manifests["rep-001-fen-rgb.yaml"] = build_manifest(
        "rep-001-fen-rgb",
        ["e2e", "real-provider", "rep-001", "multimodal"],
        positions,
        vision_model,
        "chess.direct",
        fen_rgb_obs,
        vision=True,
    )

    manifests["ground-001-free.yaml"] = build_manifest(
        "ground-001-free",
        ["e2e", "real-provider", "ground-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
    )
    manifests["ground-001-legal-first.yaml"] = build_manifest(
        "ground-001-legal-first",
        ["e2e", "real-provider", "ground-001"],
        positions,
        text_model,
        "chess.grounded",
        grounded_obs,
        declared_assistance="H3",
    )
    manifests["ground-001-reason-first.yaml"] = build_manifest(
        "ground-001-reason-first",
        ["e2e", "real-provider", "ground-001"],
        positions,
        text_model,
        "chess.reason_then_ground",
        reason_obs,
        declared_assistance="H3",
    )

    persona = {"system_instructions": "You are a Grandmaster. Play with authority."}
    manifests["skill-001-baseline.yaml"] = build_manifest(
        "skill-001-baseline",
        ["e2e", "real-provider", "skill-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
    )
    manifests["skill-001-persona.yaml"] = build_manifest(
        "skill-001-persona",
        ["e2e", "real-provider", "skill-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
        declared_knowledge="K1",
        prompt=persona,
    )
    manifests["skill-001-correct.yaml"] = build_manifest(
        "skill-001-correct",
        ["e2e", "real-provider", "skill-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
        declared_knowledge="K4",
        knowledge_packets=("skill-001-s4-najdorf-plans",),
    )
    manifests["skill-001-wrong.yaml"] = build_manifest(
        "skill-001-wrong",
        ["e2e", "real-provider", "skill-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
        declared_knowledge="K4",
        knowledge_packets=("skill-001-s5-wrong-plausible",),
    )
    manifests["skill-001-irrelevant.yaml"] = build_manifest(
        "skill-001-irrelevant",
        ["e2e", "real-provider", "skill-001"],
        positions,
        text_model,
        "chess.direct",
        fen_obs,
        declared_knowledge="K1",
        knowledge_packets=("skill-001-s6-irrelevant",),
    )

    manifests["mm-002-consistent.yaml"] = build_manifest(
        "mm-002-consistent",
        ["e2e", "real-provider", "mm-002", "multimodal"],
        positions,
        vision_model,
        "chess.direct",
        fen_rgb_obs,
        vision=True,
    )
    manifests["mm-002-conflict.yaml"] = build_manifest(
        "mm-002-conflict",
        ["e2e", "real-provider", "mm-002", "multimodal"],
        positions,
        vision_model,
        "chess.direct",
        {
            "position": {"fen": True},
            "side_to_move": True,
            "move_number": True,
            "history": {"mode": "none"},
            "image": {
                "enabled": True,
                "orientation": "white",
                "coordinates": True,
                "fen_override": "__conflict_auto__",
            },
            "modality_authority": "text",
        },
        vision=True,
    )

    for filename, content in manifests.items():
        (SUITE_DIR / filename).write_text(content, encoding="utf-8")
        print("wrote", filename)
    print("corpus sha256:", corpus_sha)


if __name__ == "__main__":
    main()
