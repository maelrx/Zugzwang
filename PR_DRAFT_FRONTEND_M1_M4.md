# PR Draft: Frontend Migration (M1-M4)

## Title
`feat(frontend): FastAPI + React migration foundation (M1-M4)`

## Summary

This PR starts the frontend migration from Streamlit to a split architecture:
- FastAPI HTTP adapter over existing engine services
- Vite + React + TypeScript frontend shell

Included milestones:
- M1: FastAPI read-only scaffold and CLI `zugzwang api`
- M2: job write endpoints and SSE log streaming
- M3: React frontend shell with router/query providers and page scaffolds
- M4: OpenAPI-generated TS schema, typed API client, query hooks, and first live API integrations

## Why

- Align implementation with `techdocs/FRONTEND_ARCHITECTURE.md`
- Keep engine core unchanged while replacing the presentation layer
- Improve maintainability and reviewability with explicit API contracts

## Scope

### Backend API
- Added `zugzwang/api/` package:
  - `main.py`, `deps.py`, `schemas.py`, `sse.py`
  - `routes/{configs,env,jobs,runs}.py`
- Added new CLI command:
  - `zugzwang api --host --port --reload`
- Added optional dependency group:
  - `api = [fastapi, uvicorn, sse-starlette]`
- Added API tests:
  - `tests/api/test_read_only_routes.py`
  - `tests/api/test_job_write_and_sse.py`

### Frontend
- Added `zugzwang-ui/` project (Vite + React + TS)
- Added initial architecture:
  - TanStack Router + TanStack Query
  - App shell and route skeletons
- Added API contract workflow:
  - `openapi-typescript` + generated `src/api/schema.ts`
  - `npm run generate-types`
- Added typed API layer:
  - `src/api/client.ts`
  - `src/api/types.ts`
  - `src/api/queries/*`
- Wired live reads into pages:
  - Dashboard, Jobs, Run Lab, Runs, Settings

## Validation

### Backend
- `python -m pytest -q` passes

### Frontend
- `npm run typecheck` passes
- `npm run lint` passes
- `npm run build` passes

## Invariants respected

- No engine business logic moved to frontend
- API is thin adapter over existing service layer
- Existing CLI commands (`run`, `play`, `evaluate`, `env-check`) unchanged
- Existing run artifacts under `results/runs/*` unchanged
- SSE used for unidirectional streaming (`/api/jobs/{job_id}/logs`)

## Risks / Notes

- Streamlit is still present (intentional at this stage)
- `schema.ts` must be regenerated when API schema changes
- `configs/validate` and `configs/preview` POST routes are pending for next milestone

## Next milestones (follow-up PRs)

- M5: run detail + replay route tree + job detail page
- M6: board replay and ply-level insights
- M7: full Run Lab launch flow + SSE terminal UX
- M8: dashboard/compare/evaluation polish and parity
- M9: Streamlit removal

## Reviewer checklist

- [ ] API route contracts match `FRONTEND_ARCHITECTURE.md`
- [ ] No business logic moved out of engine modules
- [ ] SSE behavior sane for long-running jobs
- [ ] Query hooks use generated OpenAPI types
- [ ] Build/test commands reproduce locally

