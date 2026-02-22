# Frontend Migration Roadmap (FastAPI + React)

Status: in progress (M1, M2, M3, M4 completed; M5 partial)
Owner: frontend migration track
Branch: feat/frontend-fastapi-react-migration
Source of truth docs:
- ../techdocs/FRONTEND_ARCHITECTURE.md
- ../techdocs/TECHNICAL_ARCHITECTURE_REFINED.md
- ../techdocs/IMPLEMENTATION_PLAYBOOK.md
- ROADMAP_STATUS.md

## 1. Goal

Replace the current Streamlit UI with:
- FastAPI API layer in Python (thin adapter over existing services)
- Vite + React + TypeScript frontend in `zugzwang-ui/`

Keep engine layers unchanged and preserve artifact reproducibility.

## 2. Current baseline (confirmed in codebase)

- Streamlit UI exists and is operational:
  - `zugzwang/ui/app.py`
  - `zugzwang/ui/pages/*`
  - `zugzwang/ui/services/*`
- CLI still exposes `zugzwang ui` in `zugzwang/cli.py`
- FastAPI adapter exists:
  - `zugzwang/api/*` with runs/jobs/configs/env routes
  - CLI command: `zugzwang api`
- React frontend exists:
  - `zugzwang-ui/*` with router/query shell and typed API layer
- Existing UI service logic already encapsulates key operations:
  - config preview/validation
  - run/play/evaluate job starts
  - artifact loading
  - replay frame construction
  - job lifecycle and local JSONL tracking

## 3. Non-negotiable invariants

1. No business logic moves to frontend.
2. FastAPI routes are thin adapters over existing services.
3. Frontend consumes API only, never filesystem directly.
4. Types in frontend are generated from OpenAPI schema.
5. SSE is the only streaming primitive for live logs.
6. Existing CLI commands (`run`, `play`, `evaluate`, `env-check`) remain backward compatible.
7. Existing artifact schema under `results/runs/*` remains unchanged.

## 4. Context-window-safe execution protocol

Use one module at a time with strict closure:
1. Implement only module scope.
2. Add/adjust tests for module scope.
3. Run targeted tests.
4. Update docs/changelog for module scope.
5. Commit.
6. Move to next module only after green checkpoint.

Guardrails:
- Max 8 touched files per commit when possible.
- No mixed refactor + feature in same commit.
- Keep a rolling checklist in this file.

## 5. Linear modular roadmap

## M0. Repo preparation and migration scaffold
Objective:
- Prepare repo for split backend/frontend development without breaking current workflows.

Tasks:
1. Add frontend migration checklist references in README.
2. Add make/just/npm task aliases for dual-server local dev (placeholder allowed).
3. Add architecture decision note: Streamlit is transitional until M9.

Exit criteria:
1. Developers can see migration scope and execution order in-repo.
2. No runtime behavior changes yet.

Tests:
1. None required beyond lint/import sanity.

Commit scope:
- docs/chore only

## M1. FastAPI skeleton (read-only API first)
Objective:
- Create API foundation and expose read-only data endpoints.

Tasks:
1. Create `zugzwang/api/` package:
   - `main.py`, `deps.py`, `schemas.py`, `sse.py`, `routes/*`
2. Add CLI command `zugzwang api` to start uvicorn.
3. Add optional dependency group in `pyproject.toml`:
   - `fastapi`, `uvicorn`, `sse-starlette`
4. Implement read-only endpoints:
   - `GET /api/runs`
   - `GET /api/runs/{run_id}`
   - `GET /api/runs/{run_id}/games`
   - `GET /api/runs/{run_id}/games/{n}`
   - `GET /api/runs/{run_id}/games/{n}/frames`
   - `GET /api/jobs`
   - `GET /api/jobs/{job_id}`
   - `GET /api/jobs/{job_id}/progress`
   - `GET /api/configs`
   - `GET /api/env-check`

Reuse strategy:
- Move or wrap current `zugzwang/ui/services/*` into `zugzwang/api/services/*`
- Keep implementation logic identical where possible.

Exit criteria:
1. `zugzwang api` starts on localhost.
2. OpenAPI available and route contracts stable.
3. Read-only flows equivalent to current Streamlit data access.

Tests:
1. Add API contract tests for all read-only routes.
2. Keep existing UI service tests passing.

Commit scope:
- backend api skeleton and read-only routes

## M2. Job mutations + SSE streaming
Objective:
- Enable run/play/evaluate operations and real-time log streaming via API.

Tasks:
1. Add write endpoints:
   - `POST /api/jobs/run`
   - `POST /api/jobs/play`
   - `POST /api/jobs/evaluate`
   - `DELETE /api/jobs/{job_id}`
2. Add SSE endpoint:
   - `GET /api/jobs/{job_id}/logs`
3. Keep subprocess + job JSONL mechanism unchanged.
4. Ensure terminal state closing semantics in SSE.

Exit criteria:
1. Jobs can be started/canceled through API.
2. Logs stream incrementally through SSE.
3. Job state transitions remain deterministic.

Tests:
1. API integration tests for POST/DELETE lifecycle.
2. SSE smoke test for line streaming and done event.
3. Regression tests for job store transitions.

Commit scope:
- backend job write paths and streaming

## M3. Frontend scaffold (Vite + React + TypeScript)
Objective:
- Establish robust frontend shell with routing and state infrastructure.

Tasks:
1. Create `zugzwang-ui/` app with:
   - React + TypeScript + Vite
   - TanStack Router
   - TanStack Query
   - Zustand
   - Tailwind
2. Add base layout:
   - app shell
   - sidebar navigation
   - page route skeletons
3. Configure Vite proxy to FastAPI `/api`.

Exit criteria:
1. Frontend starts locally and routes render.
2. API proxy works.

Tests:
1. Basic frontend lint/typecheck.

Commit scope:
- frontend skeleton only

## M4. OpenAPI type generation + query layer
Objective:
- Make API contract the only typing source for frontend data.

Tasks:
1. Add openapi generation script:
   - `generate-types` command using `openapi-typescript`
2. Generate `src/api/schema.ts`.
3. Build typed query hooks for jobs/runs/configs/env.
4. Add fetch client error normalization.

Exit criteria:
1. No manual duplicated API types in frontend.
2. Query hooks cover all M1/M2 routes.

Tests:
1. Frontend typecheck must pass with generated schema.
2. Query hook smoke tests (if harness available).

Commit scope:
- contract typing and query layer

## M5. Run Explorer and Run Detail pages
Objective:
- Ship the first complete user-facing inspection flow.

Tasks:
1. Implement `/runs` table with search/filter.
2. Implement `/runs/:runId` tabs:
   - overview
   - games
   - config
3. Render key metrics and report summaries.

Exit criteria:
1. Existing runs can be inspected without Streamlit.
2. Core report metadata is visible and navigable.

Tests:
1. Component tests for run list/detail rendering.
2. API integration tests for run endpoints remain green.

Commit scope:
- run explorer vertical slice

## M6. Game Replay page
Objective:
- Provide practical move-by-move analysis UI with board and ply metrics.

Tasks:
1. Implement `/runs/:runId/games/:gameNumber` replay page.
2. Integrate board component and ply slider.
3. Integrate frame metrics and raw response panel.
4. Optional: MoA trace panel when data present.

Exit criteria:
1. Any recorded game can be replayed in browser.
2. Per-ply operational metrics are visible.

Tests:
1. Replay component tests.
2. API replay frame endpoint tests.

Commit scope:
- replay vertical slice

## M7. Job Monitor and Run Lab pages
Objective:
- Bring full operation flow (configure -> launch -> monitor) into frontend.

Tasks:
1. Job list/detail pages with live SSE terminal panel.
2. Run Lab page with:
   - config picker
   - override editor
   - validate/preview
   - play/run launch actions
3. Redirect flow from launch -> job detail.

Exit criteria:
1. User can run experiments end-to-end from UI.
2. Progress and logs are understandable without terminal usage.

Tests:
1. Mutation endpoint integration tests.
2. Frontend flow smoke test for launch + monitor.

Commit scope:
- operations vertical slice

## M8. Evaluation UX + dashboard + compare + settings
Objective:
- Reach full functional parity and improve analysis navigation.

Tasks:
1. Evaluation launcher and evaluated report rendering.
2. Dashboard KPIs.
3. Run comparison page.
4. Settings page with env-check status.
5. Loading/error boundary polish.

Exit criteria:
1. Run -> evaluate -> inspect loop completed in frontend.
2. All V1 pages in `FRONTEND_ARCHITECTURE.md` covered.

Tests:
1. E2E smoke scenario across core pages.
2. Regression checks for metrics rendering.

Commit scope:
- parity and polish

## M9. Streamlit deprecation and cleanup
Objective:
- Remove obsolete Streamlit layer after parity is confirmed.

Tasks:
1. Remove `zugzwang/ui/` package.
2. Remove `zugzwang ui` command from CLI.
3. Remove `ui` optional deps from `pyproject.toml`.
4. Migrate/rename remaining tests from `tests/ui` to API/backend-focused locations.
5. Update README and docs to new startup flow.

Exit criteria:
1. Streamlit no longer required.
2. API + React stack is the only supported UI path.
3. All tests pass after removal.

Tests:
1. Full test suite.
2. Startup smoke:
   - `zugzwang api`
   - frontend dev server

Commit scope:
- breaking removal (single dedicated PR section)

## 6. PR strategy (recommended)

1. PR-A: M1 + M2 (backend API foundation)
2. PR-B: M3 + M4 (frontend foundation)
3. PR-C: M5 + M6 (exploration + replay)
4. PR-D: M7 + M8 (operations + parity)
5. PR-E: M9 (streamlit removal)

## 7. Risk map and mitigations

Risk: endpoint/schema drift between backend and frontend
- Mitigation: generated types only, CI check for stale `schema.ts`

Risk: duplicated service logic during migration
- Mitigation: move service modules, avoid reimplementation

Risk: job lifecycle regressions
- Mitigation: keep existing job runtime/store internals, add route-level tests

Risk: over-large migration PRs
- Mitigation: strict module boundaries and PR slicing

## 8. Ready-to-start next action

Finish M5 + start M6:
1. Add run comparison page and baseline artifact tabs.
2. Add chess board renderer (`react-chessboard`) in replay page.
3. Add per-ply metrics panel with move-level telemetry.
4. Expand job detail UX (pause auto-scroll, stream filters).

## 9. Progress log

- 2026-02-22: M1 implemented.
  - Added FastAPI scaffold under `zugzwang/api/`.
  - Added read-only routes for runs/jobs/configs/env.
  - Added `zugzwang api` CLI command.
  - Added optional dependency group `api` and API route tests.
- 2026-02-22: M2 implemented.
  - Added write routes for `run`, `play`, `evaluate`, and `cancel`.
  - Added SSE log streaming endpoint `GET /api/jobs/{job_id}/logs`.
  - Added API tests for write operations and SSE terminal events.
- 2026-02-22: M3 implemented.
  - Added `zugzwang-ui/` Vite + React + TypeScript frontend project.
  - Added TanStack Router + TanStack Query providers and app shell.
  - Added initial page skeletons: Dashboard, Run Lab, Jobs, Runs, Settings.
  - Added Vite API proxy and Tailwind-based visual foundation.
- 2026-02-22: M4 implemented.
  - Added OpenAPI type generation workflow and generated schema file.
  - Added typed API client and query/mutation hooks.
  - Connected Dashboard, Run Lab, Jobs, Runs and Settings to live API reads.
- 2026-02-22: M5 partial implemented.
  - Added dynamic route tree for job detail, run detail and replay.
  - Added `/jobs/$jobId` page with live SSE log stream.
  - Added `/runs/$runId` page with metrics, artifacts and game navigation.
  - Added `/runs/$runId/replay/$gameNumber` replay scaffold with ply slider.
