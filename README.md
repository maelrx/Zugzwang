<div align="right">

[🇧🇷 Leia em Português](README.pt-br.md)

</div>

<div align="center">

# ♟ Zugzwang

**A reproducible research engine for pushing LLMs to their limits in chess**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Active Research](https://img.shields.io/badge/status-active%20research-orange.svg)]()
[![Based on: LLM Chess](https://img.shields.io/badge/based%20on-LLM%20Chess%20arXiv%3A2512.01992-blueviolet)](https://arxiv.org/abs/2512.01992)

*"Zugzwang" — the chess position where every move you make worsens your situation. We use this as a crucible: can LLMs reason their way out?*

</div>

---

## What is Zugzwang?

Zugzwang is a **modular, reproducible research platform** for studying how far Large Language Models can be pushed in chess using only prompt engineering, RAG, few-shot learning, chain-of-thought, tool-use, and multi-agent orchestration — **no fine-tuning**.

Chess is used not as the end goal, but as a **microscope**. The structured, verifiable nature of chess makes it an ideal domain for rigorously measuring the gap between raw LLM capability and augmented performance, move by move.

This project extends and builds upon the [LLM Chess benchmark](https://github.com/maxim-saplin/llm_chess) (Saplin et al., NeurIPS FoRLM 2025, [arXiv:2512.01992](https://arxiv.org/abs/2512.01992)) — the definitive framework for evaluating LLMs through chess play — by systematically exploring the techniques that paper identified as gaps: structured prompting, few-shot calibration, retrieval-augmented generation, and mixture-of-agents orchestration.

---

## The Research Question

> *Using only LLM manipulation techniques — system prompts, RAG, few-shot, chain-of-thought, tool-use, multi-agent orchestration — and without fine-tuning any model, how far can a general-purpose LLM be pushed in chess?*

---

## Motivation & Background

The LLM Chess paper (Saplin et al., 2025) established that:

- Most LLMs cannot beat a **random player** — they fail at instruction-following, not chess per se
- Only reasoning-enhanced models (o3, o4-mini, Grok 3 Mini) reliably win against random play
- The best model tested (o3 low) reaches only **Elo ~758** against a calibrated engine — barely above the average chess.com player
- **FEN format outperforms Unicode boards** by up to +21.7 pp for some models
- Providing **move history reduces blunders** dramatically (11.2% → 1.6% for o4-mini)
- **Mixture-of-Agents** combining strong-reasoning + strong-instruction-following models can double win rates and achieve 100% game completion

However, that benchmark used a simple, generic prompt with no few-shot examples, no RAG, no structured chain-of-thought, and no feedback-rich retry loop. Zugzwang is built to fill those gaps, rigorously and reproducibly.

Additional foundations:

- **GPT-3.5-turbo-instruct** plays at ~1750 Elo feeding raw PGN, suggesting LLMs have latent chess knowledge suppressed by instruction tuning ([Carlini, 2023](https://nicholas.carlini.com/writing/2023/chess-llm.html))
- **3 trivial few-shot examples** dramatically improve GPT-4o's chess performance ([Dynomight, 2024](https://dynomight.net/chess/))
- **Chess-playing transformers develop linear world models** of board state ([Karvonen, 2024](https://arxiv.org/abs/2403.15498))
- LLMs fail at chess primarily due to **knowledge access**, not reasoning capacity ([arXiv:2507.00726](https://arxiv.org/abs/2507.00726))

---

## Architecture

Zugzwang is built in seven progressive layers, each independently testable:

```
Layer 0 — Infrastructure      Config loading, secret management, env validation
Layer 1 — Core Game Engine     BoardManager, game loop, LLM/Random/Engine players
Layer 2 — Evaluation           Stockfish scoring, move quality, Elo MLE estimation
Layer 3 — Strategy             Prompt library, context assembly, few-shot, validation
Layer 4 — Knowledge / RAG      Phase-aware retrieval: openings, tactics, endgames
Layer 5 — Multi-Agent          Capability-MoA, specialist agents, hybrid phase router
Layer 6 — Experiment Runner    Batch execution, resume, budget guardrails, scheduling
Layer 7 — Analysis             Statistics, plots, reports, React dashboard
```

**Key design invariants:**
- No illegal move is ever applied to the board
- Stockfish evaluation is **never** exposed to the LLM during live play
- Every game artifact is self-contained and reproducible from its seed
- Config is immutable after an experiment starts

---

## Repository Layout

```
zugzwang-engine/
├── zugzwang/
│   ├── core/           # BoardManager, game loop, players, protocol
│   ├── providers/      # Anthropic, OpenAI, Google, z.ai, mock
│   ├── evaluation/     # Stockfish, move quality, Elo, metrics
│   ├── strategy/       # Prompts, context assembler, few-shot, validator
│   ├── knowledge/      # RAG: indexer, retriever, embeddings, vectordb
│   │   └── sources/    #   ECO openings, Lichess heuristics, endgames
│   ├── agents/         # Capability MoA, tactical, positional, endgame, critic
│   ├── experiments/    # Runner, scheduler, tracker, resume
│   ├── analysis/       # Statistics, plots, reports
│   └── api/            # FastAPI layer (replaces Streamlit)
├── zugzwang-ui/        # Vite + React + TypeScript frontend
├── configs/
│   ├── defaults.yaml
│   ├── baselines/      # benchmark_compat.yaml, best_known_start.yaml
│   ├── ablations/      # Experiment condition configs
│   └── models/         # Per-model overrides
├── data/               # ECO, puzzles, annotated games, vectordb (gitignored)
├── results/            # Run artifacts and reports (gitignored)
└── tests/
```

---

## Quickstart

**Prerequisites:** Python 3.11+, a provider API key (or use the `mock` provider for local tests), and optionally [Stockfish](https://stockfishchess.org/download/) for evaluation.

```bash
# Install
pip install -e .[dev]

# Validate environment
zugzwang env-check --config configs/baselines/best_known_start.yaml

# Dry run (no API calls, no games)
zugzwang run --config configs/baselines/best_known_start.yaml --dry-run

# Play a single game
zugzwang play --config configs/baselines/best_known_start.yaml

# Run a full experiment (30 games, saves artifacts to results/)
zugzwang run --config configs/baselines/best_known_start.yaml

# Evaluate move quality with Stockfish
zugzwang evaluate --run-dir results/runs/<run-id>

# Start the API server
zugzwang api
```

### Environment Setup

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.
# For Stockfish: set STOCKFISH_PATH=/path/to/stockfish
```

---

## CLI Reference

| Command | Description |
|---|---|
| `zugzwang run --config <path>` | Run a full experiment |
| `zugzwang run --config <path> --dry-run` | Validate config without running |
| `zugzwang run --config <path> --resume` | Resume latest matching run |
| `zugzwang run --config <path> --resume-run-id <id>` | Resume specific run |
| `zugzwang play --config <path>` | Play a single game interactively |
| `zugzwang env-check --config <path>` | Validate provider credentials |
| `zugzwang evaluate --run-dir <path>` | Post-run Stockfish evaluation |
| `zugzwang api` | Start the API server (port 8000) |

### Config Overrides

Any config key can be overridden inline with `--set`:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set players.black.model=claude-opus-4-5 \
  --set strategy.board_format=fen \
  --set strategy.few_shot.enabled=true \
  --set strategy.few_shot.num_examples=3
```

---

## Key Features

### Two Baselines

| Baseline | Config | Purpose |
|---|---|---|
| `benchmark_compat` | `configs/baselines/benchmark_compat.yaml` | Faithful reproduction of LLM Chess protocol |
| `best_known_start` | `configs/baselines/best_known_start.yaml` | Direct mode + FEN + legal moves + history (best empirical config) |

### Strategy Pipeline

The `strategy` block controls everything the LLM sees:

```yaml
strategy:
  board_format: fen          # fen | ascii | combined | unicode (default: fen)
  provide_legal_moves: true
  provide_history: last_n
  history_length: 10
  few_shot:
    enabled: true
    num_examples: 3
    phase_specific: true     # Different examples per opening/middlegame/endgame
  validation:
    enabled: true
    max_retries: 3
    feedback_level: rich     # minimal | moderate | rich
```

### RAG (Phase 4 — Available)

Phase-aware knowledge retrieval from local deterministic sources:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.rag.enabled=true \
  --set strategy.rag.max_chunks=3 \
  --set strategy.rag.include_sources.eco=true \
  --set strategy.rag.include_sources.lichess=true \
  --set strategy.rag.include_sources.endgames=true
```

Sources: ECO opening principles, Lichess tactical/positional heuristics, endgame theory.

RAG ablation config: `configs/ablations/rag_variants.yaml`

### Multi-Agent Modes (Phase 5 — Available)

Mixture-of-Agents orchestration currently supports three config-level modes:
- `capability_moa`: capability-style proposers (e.g. reasoning/compliance/safety)
- `specialist_moa`: specialist proposers (tactical/positional/endgame)
- `hybrid_phase_router`: proposer roles routed by game phase

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.multi_agent.enabled=true \
  --set strategy.multi_agent.mode=capability_moa \
  --set strategy.multi_agent.proposer_count=2
```

Available ablation configs:
- `configs/ablations/moa_capability.yaml`
- `configs/ablations/moa_specialist.yaml`
- `configs/ablations/moa_hybrid_phase.yaml`

Role-level model routing (same provider, per-role model overrides):

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.multi_agent.enabled=true \
  --set strategy.multi_agent.mode=hybrid_phase_router \
  --set strategy.multi_agent.provider_policy=role_model_overrides \
  --set strategy.multi_agent.role_models.aggregator=mock-1
```

### Budget & Reliability Guardrails

```yaml
budget:
  max_total_usd: 5.00                         # Hard stop
  estimated_avg_cost_per_game_usd: 0.55       # For projected stop

runtime:
  timeout_policy:
    enabled: true
    min_games_before_enforcement: 5
    max_provider_timeout_game_rate: 0.30      # Stop if >30% games timeout
    min_observed_completion_rate: 0.60
    action: stop_run
```

### Engine Player (UCI)

Play against Stockfish at configurable skill levels:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set players.white.type=engine \
  --set players.white.depth=8
```

### z.ai / GLM-5 Integration

```bash
zugzwang env-check --config configs/baselines/best_known_start_zai_glm5.yaml
zugzwang play --config configs/baselines/best_known_start_zai_glm5.yaml
```

### Frontend — FastAPI + React (Phase 7 — In Progress)

The Streamlit prototype is being replaced by a proper split architecture: a **FastAPI** API server over the existing Python services, and a **Vite + React + TypeScript** frontend in `zugzwang-ui/`.

Start the API server:

```bash
pip install -e .[api]
zugzwang api                         # serves on localhost:8000
zugzwang api --reload                # dev mode with auto-reload
```

In development, run the frontend separately:

```bash
cd zugzwang-ui && npm install && npm run dev   # Vite on localhost:5173
```

In production, `zugzwang api` serves the built frontend as static files — single process, single port.

**Frontend pages:**

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Active jobs, recent runs, total spend |
| Run Lab | `/run-lab` | Configure, validate, and launch experiments |
| Job Monitor | `/jobs/:id` | Live log streaming (SSE), progress bar, cancel |
| Run Explorer | `/runs` | Browse all runs, filter, sort |
| Run Detail | `/runs/:id` | Metrics tabs, move quality, config, evaluate |
| Game Replay | `/runs/:id/games/:n` | Board replay, per-ply metrics, MoA agent trace |
| Compare | `/runs/compare` | Side-by-side run comparison with overlaid charts |
| Settings | `/settings` | Provider env check status |

**Stack:** FastAPI · Uvicorn · Vite · React 19 · TypeScript · TanStack Router · TanStack Query · Zustand · shadcn/ui · Tailwind · react-chessboard · Recharts

TypeScript types are auto-generated from the FastAPI OpenAPI schema — never written by hand:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts
```

Full architecture spec: [`techdocs/FRONTEND_ARCHITECTURE.md`](../techdocs/FRONTEND_ARCHITECTURE.md)

---

## Run Artifacts

Each run creates a directory in `results/runs/<run-id>/`:

```
results/runs/<run-id>/
├── resolved_config.yaml         # Full merged config
├── config_hash.txt              # Deterministic config fingerprint
├── _run.json                    # Run metadata (secrets redacted)
├── games/
│   ├── game_0001.json           # Per-game artifact with full move trace
│   ├── game_0002.json
│   └── ...
├── experiment_report.json       # Aggregated metrics
└── experiment_report_evaluated.json  # Move quality + Elo (after evaluate)
```

Each `GameRecord` includes: move sequence, retry metadata, token usage, per-move latency, cost, termination reason, and RAG/MoA traces when enabled.

---

## Experimental Roadmap

| Phase | Status | What it enables |
|---|---|---|
| Phase 0 — Bootstrap | ✅ Done | Reproducible config, CLI, env validation |
| Phase 1 — Core Engine | ✅ Done | Legal games, all player types, protocol modes |
| Phase 2 — Evaluation | ✅ Functional | Stockfish scoring, ACPL, Elo MLE, blunder rate |
| Phase 3 — Strategy | ✅ Functional | Prompts, context assembly, few-shot, validation |
| Phase 4 — RAG | ✅ MVP | Phase-aware local retrieval, ablation configs |
| Phase 5 — Multi-Agent | 🔄 Baseline+ | Capability, specialist, and hybrid phase-router MoA modes |
| Phase 6 — Experiment Runner | 🔄 Partial | Batch + resume + budget; queue scheduler pending |
| Phase 7 — Analysis | 🔄 Partial | FastAPI + React dashboard in progress |

**Next targets:** FastAPI + React frontend (replacing Streamlit), specialist/hybrid MoA, queue scheduler, comparative visualizations.

---

## Development

```bash
# Install with dev dependencies
pip install -e .[dev]

# Run all tests
pytest -q

# Install with API dependencies
pip install -e .[api]
zugzwang api --host 127.0.0.1 --port 8000
```

Tests cover: board legality, config hashing, move parsing, retry policies, Elo math, RAG retrieval, MoA orchestration, runner resume/dedup, budget enforcement.

---

## References

### Primary References

1. **Kolasani, S., Saplin, M. et al.** (2025). *LLM CHESS: Benchmarking Reasoning and Instruction-Following in LLMs through Chess.* NeurIPS FoRLM 2025. [arXiv:2512.01992](https://arxiv.org/abs/2512.01992) · [Code](https://github.com/maxim-saplin/llm_chess)

2. **Karvonen, A.** (2024). *Emergent World Models and Latent Variable Estimation in Chess-Playing Language Models.* COLM 2024. [arXiv:2403.15498](https://arxiv.org/abs/2403.15498)

3. **Feng, X. et al.** (2023). *ChessGPT: Bridging Policy Learning and Language Modeling.* NeurIPS 2023. [arXiv:2306.09200](https://arxiv.org/abs/2306.09200)

4. **Zhang, Y. et al.** (2025). *Complete Chess Games Enable LLM Become A Chess Master.* NAACL 2025. [arXiv:2501.17186](https://arxiv.org/abs/2501.17186)

5. **Monroe, D. & Leela Chess Zero Team** (2024). *Mastering Chess with a Transformer Model.* [arXiv:2409.12272](https://arxiv.org/abs/2409.12272)

6. **Ruoss, A. et al.** (2024). *Amortized Planning with Large-Scale Transformers: A Case Study on Chess.* NeurIPS 2024. [arXiv:2402.04494](https://arxiv.org/abs/2402.04494)

7. **Anonymous** (2025). *Can Large Language Models Develop Strategic Reasoning? Post-training Insights from Learning Chess.* [arXiv:2507.00726](https://arxiv.org/abs/2507.00726)

### Blog Posts & Analyses

8. **Carlini, N.** (2023). *Playing chess with large language models.* [nicholas.carlini.com](https://nicholas.carlini.com/writing/2023/chess-llm.html)

9. **Dynomight** (2024). *Something weird is happening with LLMs and chess.* [dynomight.net](https://dynomight.net/chess/)

10. **Dynomight** (2024). *OK, I can partly explain the LLM chess weirdness now.* [dynomight.net](https://dynomight.net/chess2/)

11. **Karvonen, A.** (2024). *Chess-GPT's Internal World Model.* [adamkarvonen.github.io](https://adamkarvonen.github.io/machine_learning/2024/01/03/chess-world-models.html)

---

## License

MIT. See [LICENSE](LICENSE).

---

<div align="center">
<sub>Built with rigor, curiosity, and a deep respect for the game.</sub>
</div>
