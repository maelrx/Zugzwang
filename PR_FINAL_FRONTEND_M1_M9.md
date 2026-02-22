# feat(frontend): complete FastAPI + React migration (M1-M9)

## Summary

This PR completes the frontend migration roadmap from the legacy Streamlit UI to a split architecture:

- Backend API: `zugzwang/api` (FastAPI)
- Frontend app: `zugzwang-ui` (Vite + React + TypeScript)

It delivers end-to-end parity for operations and analysis flows, removes the deprecated Streamlit package, and migrates tests and docs to the new stack.

## Scope

### 1. FastAPI backend (read + write)

- Added read endpoints for environment checks, runs, artifacts, replay frames, and summaries.
- Added write endpoints for run launch, evaluation launch, cancellation, and SSE log streaming.
- Kept job lifecycle persisted in `results/ui_jobs/jobs.jsonl`.
- Added production static serving integration from `zugzwang api`.

Key files:
- `zugzwang/api/main.py`
- `zugzwang/api/routes/*.py`
- `zugzwang/api/services/*.py`
- `zugzwang/api/schemas.py`
- `zugzwang/api/sse.py`

### 2. React frontend shell and pages

- Added routed app shell and typed API client.
- Implemented core pages:
  - Dashboard
  - Run Lab
  - Job Monitor / Job Detail
  - Run Explorer / Run Detail
  - Game Replay
  - Compare
  - Settings
- Added replay telemetry visualization and run comparison cards.
- Added smoke/integration coverage for page navigation and data flows.

Key files:
- `zugzwang-ui/src/router.tsx`
- `zugzwang-ui/src/ui/pages/*.tsx`
- `zugzwang-ui/src/api/*`
- `zugzwang-ui/scripts/smoke.mjs`

### 3. Streamlit deprecation and cleanup (M9)

- Removed legacy package `zugzwang/ui/*`.
- Removed CLI command `zugzwang ui`.
- Migrated service/runtime usage to `zugzwang/api/*`.
- Migrated tests from `tests/ui/*` to API/backend locations:
  - `tests/api/test_config_service.py`
  - `tests/api/test_job_store.py`
  - `tests/api/test_replay_service.py`
  - `tests/integration/test_api_services.py`
- Removed obsolete optional dependency group:
  - `[project.optional-dependencies].ui` in `pyproject.toml`.

## Behavior and compatibility notes

- `zugzwang api` is now the GUI backend entrypoint.
- In production mode, built frontend assets are served by FastAPI.
- Existing run artifacts contract is preserved (`results/runs/*` unchanged).
- Breaking change:
  - `zugzwang ui` no longer exists.

## Validation executed

### Python

```bash
python -m pytest -q
```

Result: pass (`1 skipped`, no failures).

### Frontend

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

Result: pass.

### API + frontend smoke

```bash
zugzwang api --host 127.0.0.1 --port 8000
cd zugzwang-ui
npm run smoke
```

Result: pass for env-check, runs index, jobs, configs, preview, run summary, game detail, replay frames.

## Documentation updates

- Updated migration and roadmap status:
  - `FRONTEND_MIGRATION_ROADMAP.md`
  - `ROADMAP_STATUS.md`
- Updated both READMEs to reflect current architecture and stack:
  - `README.md`
  - `README.pt-br.md`

## Commit set (main milestones)

- `bb94cd9` API read scaffold + `zugzwang api` command
- `9ed9c77` API write endpoints + SSE logs
- `37c98ab` React app shell scaffold
- `1dcc346` typed API client/query hooks
- `4e4d615` run/job detail routes and replay scaffold
- `4a724a1` chessboard replay + per-ply telemetry
- `7768942` compare + evaluation launcher
- `038b726` run-lab validation + launch
- `e47e4f2` M8 parity (dashboard/eval UX)
- `18b61d2` phase visualizations + smoke
- `83f1d42` move-quality analytics + run-lab smoke
- `9d29217` navigation smoke tests
- `c807479` API services decoupled from `zugzwang.ui`
- `8d4650e` M9 streamlit removal + test migration
- `e86d708` docs consistency fix (stack section)

## Reviewer checklist

- [ ] Confirm `zugzwang api` starts and serves OpenAPI.
- [ ] Confirm frontend dev server works (`npm run dev`).
- [ ] Confirm production serving works after `npm run build`.
- [ ] Confirm run launch, log streaming, and cancel flows.
- [ ] Confirm replay and compare pages with existing artifacts.
- [ ] Confirm no regressions in CLI core commands (`run/play/evaluate/env-check`).
