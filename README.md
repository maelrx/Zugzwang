# Zugzwang Engine

Research-first chess LLM experimentation engine.

Current scope (initial build):
- Deterministic config loading and hashing.
- Environment validation for provider credentials.
- Core game loop with legal move guarantees.
- Protocol support: `direct` and `agentic_compat`.
- Minimal experiment runner with reproducible artifacts.
- Cost tracking per move/game and run-level budget guardrail.

## Quickstart

```bash
python -m pip install -e .[dev]
zugzwang run --config configs/baselines/best_known_start.yaml --dry-run
zugzwang play --config configs/baselines/best_known_start.yaml
pytest -q
```

For GUI:

```bash
python -m pip install -e .[ui]
zugzwang ui
```

## Commands

- `zugzwang run --config <path> --dry-run`
- `zugzwang run --config <path>`
- `zugzwang run --config <path> --resume`
- `zugzwang run --config <path> --resume-run-id <run-id>`
- `zugzwang play --config <path>`
- `zugzwang env-check --config <path>`
- `zugzwang evaluate --run-dir <results/run-id>`
- `zugzwang ui`

## Resume/Dedup

- `--resume`: resume the latest run with matching `experiment.name` + `config_hash` in the same output dir.
- `--resume-run-id <run-id>`: resume a specific run directory.
- Existing game artifacts are loaded and deduplicated by `game_number`.
- Runner continues from the next missing game number and does not rewrite completed games.

## Run Artifacts

Each run directory in `results/runs/<run-id>/` includes:
- `resolved_config.yaml`
- `config_hash.txt`
- `_run.json` (sanitized execution metadata; secrets redacted)
- `games/game_*.json`
- `experiment_report.json`
- `experiment_report_evaluated.json` (when evaluation is executed)

## GUI (Streamlit First)

V1 scope implements local single-user Ops + Replay:
- run `dry-run`, `play`, `run`, and `evaluate` from UI
- monitor jobs and logs (`results/ui_jobs/jobs.jsonl`)
- browse run artifacts under `results/runs`
- replay games with board + per-ply metrics

Run locally:

```bash
zugzwang ui --host 127.0.0.1 --port 8501
```

Recommended GUI workflow:
1. `Guided Flow`: quick onboarding and page shortcuts.
2. `Run Lab`: select baseline, apply presets/overrides, launch job.
3. `Job Monitor`: track status/logs and validate completion.
4. `Run Explorer`: inspect artifacts and compare runs.
5. `Game Replay` and `Evaluation`: analyze move-level behavior and quality metrics.

## z.ai / GLM-5 Setup

1. Create `.env` from `.env.example` and set `ZAI_API_KEY`.
2. Keep `ZAI_BASE_URL=https://api.z.ai/api/coding/paas/v4` for Coding Plan API.
3. Use baseline `configs/baselines/best_known_start_zai_glm5.yaml`.
4. Set `ZAI_PRICING_MODE`:
   - `standard` to estimate USD from public z.ai token pricing.
   - `coding_plan` if your calls are covered by plan quota and you want marginal cost `0`.

Examples:

```bash
python -m zugzwang.cli env-check --config configs/baselines/best_known_start_zai_glm5.yaml
python -m zugzwang.cli play --config configs/baselines/best_known_start_zai_glm5.yaml --set runtime.max_plies=40
python -m zugzwang.cli run --config configs/baselines/best_known_start_zai_glm5.yaml --dry-run
python -m zugzwang.cli evaluate --run-dir results/runs/<run-id> --player-color black
```

## Budget Guardrail

- `budget.max_total_usd` is mandatory and enforced in the runner.
- Runner stops scheduling new games when:
  - spent budget has reached cap, or
  - projected final spend exceeds cap (based on configured/observed average cost).
- Optional config: `budget.estimated_avg_cost_per_game_usd` for stronger dry-run projection.

## Timeout / Reliability Guardrail

Optional runtime policy to stop unstable runs early:

- `runtime.timeout_policy.enabled`
- `runtime.timeout_policy.min_games_before_enforcement`
- `runtime.timeout_policy.max_provider_timeout_game_rate`
- `runtime.timeout_policy.min_observed_completion_rate`
- `runtime.timeout_policy.action` (currently `stop_run`)

When enabled, the runner can stop a condition early if:
- too many games include provider timeout errors, or
- observed completion collapses below threshold.

## RAG (Phase 4 MVP)

RAG is now available as an optional strategy block with local, deterministic retrieval.

- Sources currently included:
  - `eco` (opening principles)
  - `lichess` (tactical/positional heuristics)
  - `endgames` (endgame principles)
- Retrieval is phase-aware (`opening`, `middlegame`, `endgame`) and can be toggled per run with config only.
- Retrieved snippets are injected into the direct prompt and obey prompt compression rules (`context.compression_order` can include `rag`).

Example toggle via overrides:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.rag.enabled=true \
  --set strategy.rag.max_chunks=3 \
  --set strategy.rag.include_sources.eco=true \
  --set strategy.rag.include_sources.lichess=true \
  --set strategy.rag.include_sources.endgames=true
```

RAG ablation starter config:

- `configs/ablations/rag_variants.yaml`

Retrieval telemetry is now persisted per move and summarized at run level:
- move fields: `retrieval_enabled`, `retrieval_hit_count`, `retrieval_latency_ms`, `retrieval_sources`, `retrieval_phase`
- report fields: `retrieval_hit_rate`, `avg_retrieval_hits_per_move`, `avg_retrieval_latency_ms`, `retrieval_hit_rate_by_phase`

## Capability MoA (Phase 5 baseline)

Initial capability-based multi-agent orchestration is now available in direct mode:

- proposer sub-calls with role prompts (for example: `reasoning`, `compliance`)
- one aggregator sub-call to select the final legal move
- sub-call traces persisted per move in `agent_trace`
- fallback policy: if aggregator output is invalid, use proposer majority candidate when legal

Enable via config/overrides:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.multi_agent.enabled=true \
  --set strategy.multi_agent.mode=capability_moa \
  --set strategy.multi_agent.proposer_count=2
```

MoA baseline config:

- `configs/ablations/moa_capability.yaml`

MoA telemetry:
- move fields: `decision_mode` (`single_agent` or `capability_moa`) and `agent_trace`
- report field: `moa_move_share`

## Stockfish Evaluation (Phase 2)

- Evaluation command reads a completed run directory and creates `experiment_report_evaluated.json`.
- Requires Stockfish binary:
  - set `STOCKFISH_PATH` in `.env`, or
  - set `evaluation.stockfish.path` in config, or
  - keep `stockfish` available on `PATH`.
- Local non-admin setup used in this repo: `tools/stockfish/stockfish/stockfish-windows-x86-64.exe`.
- Non-admin Windows install shortcut (already applied here): download Stockfish release zip into `tools/stockfish/` and set `STOCKFISH_PATH` in `.env`.

## Engine Player (UCI)

`players.<color>.type=engine` now uses a real UCI engine move call (defaults to `STOCKFISH_PATH`/`stockfish`).

Optional player keys:
- `path` (engine binary path)
- `depth` (search depth, default `8`)
- `movetime_ms` (fixed move time; overrides depth when set)
- `threads` (default `1`)
- `hash_mb` (default `64`)

Example:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set players.black.type=engine \
  --set players.black.name=stockfish_black \
  --set players.black.path=tools/stockfish/stockfish/stockfish-windows-x86-64.exe \
  --set players.black.depth=10
```

### Optional auto-evaluation at end of `run`

Enable in config/overrides:

```bash
python -m zugzwang.cli run --config configs/baselines/best_known_start.yaml \
  --set evaluation.auto.enabled=true \
  --set evaluation.auto.player_color=black
```

Available keys:
- `evaluation.auto.enabled` (`true|false`)
- `evaluation.auto.player_color` (`white|black`)
- `evaluation.auto.opponent_elo` (optional float)
- `evaluation.auto.elo_color_correction` (float, default `0.0`)
- `evaluation.auto.output_filename` (default `experiment_report_evaluated.json`)
- `evaluation.auto.fail_on_error` (`true|false`, default `false`)

## Notes

- Default protocol is `direct`.
- Default board format is `fen`.
- `mock` provider works without API keys and is useful for local tests.
- Development status snapshot: `ROADMAP_STATUS.md`.
