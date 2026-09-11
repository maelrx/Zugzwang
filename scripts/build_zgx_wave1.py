#!/usr/bin/env python3
"""ZGX wave 1 builder: S12/T6 fixtures + native wave-1 manifests.

Sources: arena-corpus development positions (dossier §11 cases, full move
prefixes) + resume8/J success positions. The eight historical diagnostic
fixtures are NOT reused; S12/T6 freeze NEW development-grade sets, and the
gabarito lives in a separate evaluator-side directory.

Wave 1 order (plano 28 §8): 02 -> 03 -> 01 -> 12 -> 13 -> 15 -> 16 (S12
paired, AB/BA alternated per position) and 20 (T6 episodes, M0 vs M2).
Everything runs reasoning_effort=low on the authorized Muse route.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "experiments" / "zgx"

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@dataclass(frozen=True)
class Position:
    pid: str
    family: str
    source: str
    move_prefix: tuple[str, ...]
    anchor_fen: str  # reference only; manifests replay the prefix


def _load_s12() -> list[Position]:
    sources = json.loads(
        (ROOT / "experiments" / "zgx" / "fixtures" / "s12_sources.json").read_text()
    )
    positions = []
    for pid, entry in sources.items():
        family = pid.split("-", 1)[1]
        positions.append(
            Position(
                pid=pid,
                family=family,
                source=f"{entry['source']}:{entry['case']}",
                move_prefix=tuple(entry["move_prefix"]),
                anchor_fen=entry["anchor_fen"],
            )
        )
    positions.sort(key=lambda pos: pos.pid)
    return positions


S12 = _load_s12()
T6_STARTS = [S12[i] for i in (0, 2, 4, 6, 8, 10)]  # one per family pair

BASE_TASK = """  task:
    plugin: chess.tasks
    version: "0.1"
    config:
      cognitive_interaction_mode: native_tools
{task_body}      backend_config:
        base_url: http://127.0.0.1:8788/v1
        provider_id: opencode-router
        timeout_seconds: 420
        profile: openai-responses
        allow_private_network: true
        reasoning_effort: low
        default_max_output_tokens: {max_tokens}
"""

MANIFEST = """# ZGX-{zgx:02d} onda 1 — {arm_label} | {pid} ({family}) | {ab}
# Posição-fonte: {source}. Par pareado; esforço LOW; rota muse congelada.
# {comment}
api_version: zgw.dev/v1alpha1
kind: Experiment

metadata:
  name: {name}
  tags: [zgx, wave1, real, {tags}, {family_tag}]

spec:
  seed: {seed}

{task_block}
  players:
    white:
      model:
        backend: provider.openai_compatible
        provider: opencode-router
        model: muse-spark-1.3-contributor
        strategy: chess.cognitive_navigation
    black:
      policy:
        plugin: {opponent_plugin}
{opponent_extra}
  protocol:
    declared_assistance: H4
    declared_knowledge: K0
    observation:
      position: {{fen: true, ascii: false}}
      side_to_move: true
      move_number: true
      history: {{mode: last_n, plies: 6, notation: uci}}
    retries:
      transport: 4
      parse: 1
      illegal: 4

  budget:
    max_calls: {max_calls}
    max_concurrent_episodes: 1
    max_attempts: 1

  evaluation: []

  artifacts:
    raw_requests: true
    raw_responses: true
    redact: standard
"""

NEUTRAL_DIRECTIVE = """        directive: >-
          Choose the best move for the side to move. Use board_observe on the
          root, investigate with board_expand as needed — an expansion returns
          the child's position package, and you may expand FROM a child to
          examine the adversary's reply. Then finalize with board_finalize on
          the ROOT node with the chosen action_id. The legal list order is not
          a quality ranking.
"""

ARM_CONFIGS = {
    # ZGX-02: N0 (no preload, no inline) vs N1 (preload, no inline)
    "zgx02-a": {
        "rounds": 4,
        "preload": False,
        "preload_expand": 0,
        "inline": False,
        "max_tokens": 8192,
        "comment": "controle N0: raiz por board_observe, expand SEM pacote-filho.",
    },
    "zgx02-b": {
        "rounds": 4,
        "preload": True,
        "preload_expand": 0,
        "inline": False,
        "max_tokens": 8192,
        "comment": "tratamento N1: raiz pré-carregada no request inicial.",
    },
    # ZGX-03: N1 vs N2 (inline child package)
    "zgx03-a": {
        "rounds": 4,
        "preload": True,
        "preload_expand": 0,
        "inline": False,
        "max_tokens": 8192,
        "comment": "controle N1: expand devolve só referência do filho.",
    },
    "zgx03-b": {
        "rounds": 4,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "comment": "tratamento N2: expand devolve o pacote-filho inline.",
    },
    # ZGX-01: RICH1 vs N6
    "zgx01-a": {
        "rounds": 1,
        "preload": True,
        "preload_expand": 4,
        "inline": True,
        "max_tokens": 32768,
        "comment": "RICH1: UMA chamada (32k) com raiz + 4 expansões pré-carregadas.",
    },
    "zgx01-b": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "comment": "N6: até seis chamadas investigativas com pacote-filho inline.",
    },
    # ZGX-12..16: N6 neutral vs N6 + procedure directive
    "zgx12-a": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE,
        "comment": "controle N6 prompt neutro.",
    },
    "zgx12-b": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE
        + """          PROCEDURE (conditional priorities): before preferring castling,
          development or a capture, check whether a concrete urgency exists
          (check, mate threat, a capture against your piece). A capture is a
          candidate, never an absolute priority. A forcing reply must be
          examined, not automatically chosen.
""",
        "comment": "tratamento: prioridades condicionais em vez de slogans.",
    },
    "zgx13-a": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE,
        "comment": "controle N6 prompt neutro.",
    },
    "zgx13-b": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE
        + """          PROCEDURE (capture verification): if a capture is among your
          finalists, expand it and examine ONE concrete adversary reply in the
          child state before keeping it as the choice. The obvious recapture
          is a hypothesis; also look for the strongest intermediate reply. Do
          not declare safety from the captured piece's value alone.
""",
        "comment": "tratamento: recaptura verificada antes de aceitar captura.",
    },
    "zgx15-a": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE,
        "comment": "controle N6 prompt neutro.",
    },
    "zgx15-b": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE
        + """          PROCEDURE (adversarial pass): reserve one investigation to examine
          the child position AS THE ADVERSARY: find a concrete reply that
          makes your previous choice bad. Do not confirm the plan out of
          politeness.
""",
        "comment": "tratamento: rodada explícita do ponto de vista adversário.",
    },
    "zgx16-a": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE,
        "comment": "controle N6 prompt neutro.",
    },
    "zgx16-b": {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE
        + """          PROCEDURE (king safety): before finalizing, look for the most
          dangerous immediate objection AGAINST YOUR KING after the candidate
          move (a check or mate reply). If one is plausible, execute that line
          in the sandbox before deciding. Separate an already-lost position
          from an avoidable immediate mate.
""",
        "comment": "tratamento: checagem de segurança do rei antes de finalizar.",
    },
}

SF_OPPONENT = """        plugin: chess.stockfish
        config:
          executable: /home/maelrx/.local/bin/stockfish
          elo: 1000
          allow_approximate: true
          limit: {nodes: 20000}
          options: {Threads: "1", Hash: "16"}
"""


def cognitive_block(arm: dict) -> str:
    lines = ["      cognitive:"]
    lines.append(f"        max_rounds: {arm['rounds']}")
    if arm["preload"]:
        lines.append("        preload_root: true")
    if arm["preload_expand"]:
        lines.append(f"        preload_expand_actions: {arm['preload_expand']}")
    if not arm["inline"]:
        lines.append("        inline_child_packages: false")
    directive = arm.get("directive")
    if directive:
        text = directive.rstrip()
        if text.lstrip().startswith("directive:"):
            # the directive text already carries its own YAML key + indentation
            lines.extend(text.splitlines())
        else:
            lines.append("        directive: >-")
            for line in text.splitlines():
                lines.append(f"          {line.strip()}")
    return "\n".join(lines) + "\n"


def s12_task(pid: str, pos: Position, arm: dict) -> str:
    prefix = ", ".join(pos.move_prefix)
    body = (
        f"      kind: move-selection\n      start_fen: {START_FEN}\n      move_prefix: [{prefix}]\n"
    )
    return (
        BASE_TASK.format(kind="move-selection", task_body=body, max_tokens=arm["max_tokens"])
        + cognitive_block(arm)
        + "\n"
    )


def t6_task(pos: Position) -> str:
    body = (
        f"      kind: full-game\n"
        f"      start_fen: {pos.anchor_fen}\n"
        f"      model_color: white\n"
        f"      max_plies: 7\n"
    )
    return BASE_TASK.format(kind="full-game", task_body=body, max_tokens=8192)


def write_manifest(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main() -> None:
    fixtures_dir = OUT / "fixtures"
    wave_dir = OUT / "wave1"
    gabarito_dir = OUT / "gabarito"
    for d in (fixtures_dir, wave_dir, gabarito_dir):
        d.mkdir(parents=True, exist_ok=True)

    # fixtures (player-side; NO answers)
    s12_json = [
        {
            "id": p.pid,
            "family": p.family,
            "source": p.source,
            "start_fen": START_FEN,
            "move_prefix": list(p.move_prefix),
            "anchor_fen": p.anchor_fen,
        }
        for p in S12
    ]
    (fixtures_dir / "s12.json").write_text(json.dumps(s12_json, indent=1), encoding="utf-8")
    t6_json = [
        {"id": p.pid, "source": p.source, "start_fen": p.anchor_fen, "max_model_decisions": 4}
        for p in T6_STARTS
    ]
    (fixtures_dir / "t6_starts.json").write_text(json.dumps(t6_json, indent=1), encoding="utf-8")

    # gabarito (evaluator-side ONLY; never assembled into any player prompt)
    (gabarito_dir / "README.md").write_text(
        "# GABARITO ZGX — uso exclusivo pós-hoc\n\n"
        "Este diretório nunca é lido pelo montador de prompts do jogador.\n"
        "Expectativas por família servem de sanidade mecânica; a avaliação de\n"
        "qualidade é SEMPRE Stockfish pós-hoc congelado (binário/opções fixos),\n"
        "nunca esta tabela.\n",
        encoding="utf-8",
    )
    (gabarito_dir / "s12_family_expectations.json").write_text(
        json.dumps(
            {
                "captura_boa": "posição com captura ganhadora documentada (avaliador preferia a captura)",
                "captura_ruim": "captura com sacrifício/recaptura não justificados (avaliador preferia alternativa)",
                "urgencia_rei": "urgência concreta contra o rei; lance de segurança esperado",
                "linha_risco": "captura que abre linha contra peça própria; alternativa esperada",
                "quieto_sucesso": "posição do corpus em que o lance quieto/construtivo levou ao sucesso",
                "final_conversao": "posição favorável de conversão; manter vantagem",
            },
            indent=1,
        ),
        encoding="utf-8",
    )

    # wave-1 manifests
    queue: list[str] = []
    comparisons = [
        ("zgx02", "N0", "N1"),
        ("zgx03", "N1", "N2"),
        ("zgx01", "RICH1", "N6"),
        ("zgx12", "N6-neutro", "N6+prioridades"),
        ("zgx13", "N6-neutro", "N6+recaptura"),
        ("zgx15", "N6-neutro", "N6+adversario"),
        ("zgx16", "N6-neutro", "N6+rei"),
    ]
    for zgx, a_label, b_label in comparisons:
        for idx, pos in enumerate(S12):
            pair_seed = 202690000 + idx
            ab = "AB" if idx % 2 == 0 else "BA"
            order = (
                (("a", a_label), ("b", b_label)) if ab == "AB" else (("b", b_label), ("a", a_label))
            )
            for side, label in order:
                arm = ARM_CONFIGS[f"{zgx}-{side}"]
                name = f"zgx{zgx[3:]}-{side}-{pos.pid}"
                text = MANIFEST.format(
                    zgx=int(zgx[3:]),
                    arm_label=label,
                    pid=pos.pid,
                    family=pos.family,
                    ab=ab,
                    source=pos.source,
                    comment=arm["comment"],
                    name=name,
                    tags=f"zgx{zgx[3:]}",
                    family_tag=pos.family,
                    seed=pair_seed,
                    task_block=s12_task(pos.pid, pos, arm),
                    opponent_plugin="fake.stay",
                    opponent_extra="",
                    max_calls=60,
                )
                write_manifest(wave_dir / f"{name}.yaml", text)
                queue.append(f"{name}.yaml")

    # ZGX-20: T6 episodes, M0 vs M2 (N6 base, low)
    for idx, pos in enumerate(T6_STARTS):
        pair_seed = 202680000 + idx
        ab = "AB" if idx % 2 == 0 else "BA"
        order = (("a", "M0"), ("b", "M2")) if ab == "AB" else (("b", "M2"), ("a", "M0"))
        for side, label in order:
            arm = {
                "rounds": 6,
                "preload": True,
                "preload_expand": 0,
                "inline": True,
                "max_tokens": 8192,
                "directive": NEUTRAL_DIRECTIVE,
                "comment": f"T6 {label}: episódio de 4 decisões do Muse vs SF congelado.",
            }
            cognitive = cognitive_block(arm)
            if side == "a":
                # M0: no reinjection at all
                cognitive = cognitive.replace("      cognitive:\n", "      cognitive:\n")
            else:
                # M2: structured factual note
                cognitive = cognitive.replace(
                    "      cognitive:\n",
                    "      cognitive:\n        reasoning_memory: factual\n",
                )
            task = t6_task(pos) + cognitive + "\n"
            name = f"zgx20-{side}-{pos.pid}"
            text = MANIFEST.format(
                zgx=20,
                arm_label=label,
                pid=pos.pid,
                family="memoria_t6",
                ab=ab,
                source=pos.source,
                comment=arm["comment"],
                name=name,
                tags="zgx20",
                family_tag="memoria_t6",
                seed=pair_seed,
                task_block=task,
                opponent_plugin="chess.stockfish",
                opponent_extra=SF_OPPONENT.rstrip("\n"),
                max_calls=120,
            )
            write_manifest(wave_dir / f"{name}.yaml", text)
            queue.append(f"{name}.yaml")

    # preflight (<=16 calls): N2 config + grandchild directive on a tactical position
    arm = {
        "rounds": 6,
        "preload": True,
        "preload_expand": 0,
        "inline": True,
        "max_tokens": 8192,
        "directive": NEUTRAL_DIRECTIVE
        + """          DIRECTED PREFLIGHT: (1) expand your main candidate at the root;
          (2) from the child package, expand the adversary's strongest reply
          (a grandchild); (3) then finalize on the ROOT node. This is a
          mechanism check, not a game.
""",
        "comment": "preflight ≤16 calls: rota, tool, filho, neto, causal, finalize raiz.",
    }
    pos = S12[2]  # K4: capture position
    task = s12_task(pos.pid, pos, arm)
    name = "zgx-preflight"
    text = MANIFEST.format(
        zgx=0,
        arm_label="preflight-N2",
        pid=pos.pid,
        family="preflight",
        ab="-",
        source=pos.source,
        comment=arm["comment"],
        name=name,
        tags="preflight",
        family_tag="preflight",
        seed=202600000,
        task_block=task,
        opponent_plugin="fake.stay",
        opponent_extra="",
        max_calls=16,
    )
    write_manifest(wave_dir / f"{name}.yaml", text)
    queue.insert(0, f"{name}.yaml")

    (wave_dir / "queue_order.txt").write_text("\n".join(queue) + "\n", encoding="utf-8")
    print(f"manifests: {len(queue)} (preflight 1 + S12 {7 * 12 * 2} + T6 12)")
    print("fixtures: s12.json (12), t6_starts.json (6), gabarito separado")


if __name__ == "__main__":
    main()
