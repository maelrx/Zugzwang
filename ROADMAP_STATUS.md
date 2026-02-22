# Zugzwang Engine Roadmap Status

Last updated: 2026-02-22 (engine-phase4-telemetry-phase5-moa-baseline update)

## Progress by phase

## Phase 0: Project Bootstrap
- Status: done (MVP)
- Implemented:
  - deterministic config merge + hash
  - env/secret validation
  - CLI dry-run and env-check
  - baseline config scaffolding

## Phase 1: Core Game Engine
- Status: done (MVP)
- Implemented:
  - `BoardManager` legality and terminal checks
  - player interface (`random`, `llm`, `engine` UCI-backed)
  - direct + agentic_compat protocol execution
  - provider retry/backoff handling in `LLMPlayer`
  - legal fallback (never apply illegal move)
  - game artifact writing

## Phase 2: Evaluation
- Status: partial (functional)
- Implemented:
  - real Stockfish integration (`python-chess` UCI engine adapter)
  - move quality metrics: ACPL, blunder rate, best-move agreement
  - ACPL split by phase (opening/middlegame/endgame)
  - Elo MLE estimator with 95% CI
  - evaluation command: `zugzwang evaluate --run-dir ...`
  - evaluated report artifact: `experiment_report_evaluated.json`
  - optional auto-evaluation integrated into default `run` pipeline via config (`evaluation.auto.*`)
- Missing:
  - deeper statistical reporting beyond the current summary

## Phase 3: Strategy
- Status: partial
- Implemented:
  - in-loop direct/agentic prompting + retries
  - dedicated strategy modules now active:
    - `strategy/context.py` (context assembly + compression policy)
    - `strategy/few_shot.py` (phase-aware few-shot rendering)
    - `strategy/validator.py` (move parsing/validation + feedback levels)
- Missing:
  - token-level budget enforcement (current implementation is char-budget compression)

## Phase 4: Knowledge / RAG
- Status: partial (MVP)
- Implemented:
  - deterministic local retrieval core:
    - `knowledge/embeddings.py` (sparse hashed embeddings)
    - `knowledge/vectordb.py` (in-memory similarity search)
    - `knowledge/indexer.py` (source registry and source toggles)
    - `knowledge/retriever.py` (phase-aware retrieval with cache)
  - initial data source adapters:
    - `knowledge/sources/eco.py`
    - `knowledge/sources/lichess.py`
    - `knowledge/sources/endgames.py`
  - strategy integration:
    - `strategy.rag.*` config block
    - retrieved snippets injected into direct prompt context
    - prompt compression now supports `rag` block drop
  - ablation starter config:
    - `configs/ablations/rag_variants.yaml`
  - tests:
    - retrieval unit tests
    - context integration tests for RAG inclusion/compression
    - config validation tests for `strategy.rag.*`
    - integration runner smoke with RAG enabled
- Missing:
  - external dataset ingestion pipelines (real ECO/Lichess corpora)
  - optional positional reranker and vector backend pluggability (Chroma/Qdrant)

## Phase 5: Multi-agent
- Status: partial (baseline)
- Implemented:
  - capability-MoA baseline orchestrator:
    - proposer role sub-calls
    - aggregator sub-call for final move choice
    - legal fallback to proposer majority candidate when aggregator output is invalid
  - config path:
    - `strategy.multi_agent.enabled`
    - `strategy.multi_agent.mode=capability_moa`
    - `strategy.multi_agent.proposer_count`
    - `strategy.multi_agent.proposer_roles`
    - `strategy.multi_agent.include_legal_moves_in_aggregator`
  - move-level trace persistence:
    - `decision_mode`
    - `agent_trace` (role, parse/legal, tokens, latency, cost, raw output)
  - ablation starter config:
    - `configs/ablations/moa_capability.yaml`
- Missing:
  - specialist-MoA and hybrid phase router
  - cross-agent provider routing policies

## Phase 6: Experiment runner / scheduler
- Status: partial
- Implemented:
  - completion-aware game scheduling
  - run artifacts and reproducible IDs/seeds
  - budget guardrail (hard stop + projected stop)
  - z.ai call-level cost estimation and run-level cost accounting
  - resume and dedup for interrupted runs (`--resume`, `--resume-run-id`)
  - timeout/completion reliability guardrail (`runtime.timeout_policy.*`)
- Missing:
  - queue scheduler
  - provider-aware throttling/queue policies

## Phase 7: Analysis & reporting
- Status: partial
- Implemented:
  - Streamlit GUI shell (`zugzwang ui`) with pages:
    - Home
    - Run Lab
    - Job Monitor
    - Run Explorer
    - Game Replay
    - Evaluation
  - Local subprocess job orchestration + persisted UI job tracking in `results/ui_jobs/jobs.jsonl`
  - Future hooks placeholders for Strategy/RAG/MoA/Scheduler/Research Dashboard tabs
- Missing:
  - richer comparative visualizations and publication export pipelines
  - queue/scheduler controls beyond local single-user workflow

## Recent changes (this update)
- Added Capability-MoA aggregator rationale logging:
  - `aggregator_rationale` persisted in move artifacts
  - rationale includes selection path and proposer vote context
- Added retrieval usefulness analysis in evaluated reports:
  - hit vs no-hit ACPL delta
  - best-move agreement split by retrieval hit
  - blunder-rate split by retrieval hit
  - hit-count vs centipawn-loss Pearson correlation
  - per-phase usefulness breakdown
- Added retrieval observability:
  - move-level retrieval metadata persisted in artifacts
  - report metrics:
    - `retrieval_hit_rate`
    - `avg_retrieval_hits_per_move`
    - `avg_retrieval_latency_ms`
    - `retrieval_hit_rate_by_phase`
- Added capability-MoA baseline:
  - proposer+aggregator orchestration
  - per-move `agent_trace` persistence
  - `moa_move_share` experiment-level metric
  - config validation + defaults + ablation config
- Fixed experiment completion metric bug:
  - `completion_rate` now calculated after valid/non-valid tally
- Added Phase 4 RAG MVP:
  - local, deterministic retrieval with phase-aware routing
  - strategy-level RAG toggle (`strategy.rag.enabled`) with source-level controls
  - direct prompt now supports retrieved knowledge snippets and `rag` compression
  - baseline ablation config scaffold for RAG variants
  - test coverage for retriever, config validation, prompt integration, and runner smoke
- Added runtime timeout/completion guardrail:
  - `runtime.timeout_policy.enabled`
  - `runtime.timeout_policy.min_games_before_enforcement`
  - `runtime.timeout_policy.max_provider_timeout_game_rate`
  - `runtime.timeout_policy.min_observed_completion_rate`
  - `runtime.timeout_policy.action=stop_run`
- Runner now emits:
  - `stopped_due_to_reliability`
  - `reliability_stop_reason`
  - `provider_timeout_game_rate`
  - `nonvalid_game_rate`
- Added report fields for reliability stop and rates.
- Added tests covering:
  - stop on provider-timeout rate collapse
  - stop on observed completion collapse
  - timeout policy config validation
- Added phase-6 resume/dedup implementation:
  - auto-resume latest matching run by `experiment.name + config_hash`
  - explicit resume by `run_id`
  - load and deduplicate existing game artifacts by `game_number`
  - continue from next missing game number without duplicating completed games
- Added CLI options:
  - `zugzwang run --resume`
  - `zugzwang run --resume-run-id <run-id>`
- Added tests for interruption/resume and dedup loading.
- Added provider error taxonomy (`retryable` vs fatal) and retry-aware handling in `LLMPlayer`.
- Added `_run.json` artifact with sanitized run metadata (secret redaction).
- Added integration tests with local mocked HTTP server for `provider=zai`.
- Replaced `EnginePlayer` placeholder with real UCI engine move selection (`path/depth/movetime_ms/threads/hash_mb`).
- Added optional auto-evaluation in `ExperimentRunner.run()` controlled by:
  - `evaluation.auto.enabled`
  - `evaluation.auto.player_color`
  - `evaluation.auto.opponent_elo`
  - `evaluation.auto.elo_color_correction`
  - `evaluation.auto.output_filename`
  - `evaluation.auto.fail_on_error`
- Added config validation for `evaluation.auto.*`.
- Implemented first-class strategy modules and integrated them into `LLMPlayer` direct mode:
  - structured context assembly
  - phase-aware few-shot blocks
  - feedback-level-aware retry messages
- Added tests for strategy modules and runner auto-evaluation integration.
- Added Streamlit GUI V1 (Ops + Replay) and `zugzwang ui` command.
- Added UI application services for config/run/evaluation/artifact/replay flows.
- Added local UI job lifecycle tracking (`queued/running/completed/failed/canceled`) with log tailing and cancel.
- Added phase-2 evaluator pipeline with Stockfish and Elo MLE.
- Added `evaluate` CLI command for post-run evaluation artifacts.
- Added z.ai provider integration for GLM-5 (`/chat/completions`)
- Added pricing-based USD estimation for z.ai models (standard mode)
- Added pricing mode switches:
  - `standard`
  - `coding_plan`
  - `custom` (env override rates)
- Added run-level budget guardrails:
  - stop when budget spent >= cap
  - stop when projected total > cap
- Added tests for pricing and budget stop behavior

## Next build targets (ordered)
1. Phase 5 specialist/hybrid MoA with cross-agent routing policies.
2. Phase 6 queue scheduler + provider-aware throttling.
3. Phase 7 richer comparative analysis and publication exports.
