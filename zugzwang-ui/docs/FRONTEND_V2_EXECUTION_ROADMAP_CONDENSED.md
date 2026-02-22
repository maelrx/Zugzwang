# Frontend V2 Execution Roadmap (Condensed)

Status: Active  
Owner: Frontend V2 Refactor Stream  
Branch: `feat/frontend-v2-uiux-refactor`  
Last updated: 2026-02-22

## 1. Purpose

This document is the operational source of truth for implementing the full UI/UX redesign in incremental milestones.
It condenses high-value decisions from long-form docs so implementation can move fast without repeatedly re-reading full specifications.

This file does not replace architecture/PRD documents. It defines implementation order, integration contracts, and quality gates.

## 2. Canonical Sources

Primary (authoritative):
- `D:/Zugzwang - Chess LLM Engine/techdocs/FRONTEND_REDESIGN_ARCHITECTURE_Opus.md` (workspace-level doc)
- `D:/Zugzwang - Chess LLM Engine/techdocs/FRONTEND_REDESIGN_PRD_Opus.md` (workspace-level doc)

Secondary (complementary only):
- `D:/Zugzwang - Chess LLM Engine/techdocs/UI_ARCHITECTURE_V2.md` (workspace-level doc)
- `D:/Zugzwang - Chess LLM Engine/techdocs/UI_PRD_V2.md` (workspace-level doc)

Operational context:
- `D:/Zugzwang - Chess LLM Engine/techdocs/FRONTEND_APP_USAGE_STEP_BY_STEP.md` (workspace-level doc)

Rule:
- If Opus and V2 conflict, Opus wins.

## 3. Locked Decisions

1. Information architecture baseline: Opus routes and navigation model.
2. Auto-evaluation strategy (v1): native runner auto-eval via `evaluation.auto.*` overrides, no new custom job status in first cut.
3. Rollout model: incremental and backward-compatible (no big-bang).
4. API evolution policy: additive, non-breaking only.

## 4. Current Baseline Snapshot (M0)

Backend state (already available):
- Core routes: `/api/configs`, `/api/env-check`, `/api/jobs`, `/api/runs`
- Job statuses: `queued`, `running`, `completed`, `failed`, `canceled`
- Native runner auto-eval exists in `zugzwang/experiments/runner.py` via `evaluation.auto.*`
- OpenAPI type generation script exists in UI: `npm run generate-types`

Frontend state (current):
- Routes centered on `/run-lab`, `/jobs`, `/runs`, `/settings`
- No global Zustand stores used yet
- No recharts-based system in current pages
- Existing SSE is log streaming only (`/api/jobs/{job_id}/logs`)

## 5. Target Route Map (V2)

Primary routes:
- `/dashboard`
- `/quick-play`
- `/lab`
- `/runs`
- `/runs/:runId`
- `/runs/:runId/game/:n`
- `/compare`
- `/settings`

Compatibility redirects (introduced gradually):
- `/` -> `/dashboard`
- `/run-lab` -> `/lab`
- `/jobs` -> `/dashboard` with active-jobs context
- `/jobs/:jobId` -> `/dashboard` or dedicated observability context
- `/runs/:runId/replay/:gameNumber` -> `/runs/:runId/game/:gameNumber`
- `/runs/compare` -> `/compare`

## 6. Milestone Plan and Gates

### M0 - Baseline and Execution Control

Scope:
- Create condensed roadmap (this file)
- Lock baseline decisions and rollout model
- Define commit and gate protocol

Exit gate:
- Operational roadmap committed
- Branch initialized and clean baseline recorded

### M1 - Foundation

Scope:
- AppShell V2 structure and nav model
- Semantic design tokens and shared UI primitives
- Introduce Zustand stores:
  - `preferences`
  - `notifications`
  - `compare`
  - `lab`
  - `sidebar`
- Global toast infrastructure + job watcher skeleton

Exit gate:
- Navigation shell stable and build green
- Existing key screens still reachable

### M2 - Backend Data Foundation

Scope:
- Add `GET /api/dashboard/kpis`
- Extend `GET /api/runs` for richer filtering/pagination
- Extend run payloads with inferred display fields
- Route tests + schema updates + frontend type regen

Exit gate:
- Dashboard and run lists can load from stable aggregate endpoints without UI-side N+1 patterns

### M3 - Command Center (`/dashboard`)

Scope:
- KPI strip
- Active jobs feed with progress
- Quick actions: quick play, new experiment, rerun last
- Recent runs with compare-selection entry
- Empty states and first-run guidance

Exit gate:
- Dashboard becomes the primary operational surface

### M4 - Quick Play (`/quick-play`)

Scope:
- Minimal provider/model setup with persisted defaults
- Progressive disclosure for advanced options
- Auto-eval toggle wiring through launch overrides:
  - `evaluation.auto.enabled`
  - `evaluation.auto.player_color`
  - `evaluation.auto.opponent_elo`
- Live board updates:
  - first implementation can use polling fallback
  - preferred target: move SSE endpoint

Exit gate:
- Single-game flow is low-friction and returns evaluated results when configured

### M5 - Experiment Lab (`/lab`)

Scope:
- 3-panel lab layout
- Template + model flow with automatic validation/preview (debounced)
- Launch orchestration with cost visibility
- Clone/pre-populate from existing run

Exit gate:
- Standard experiment launch flow reduced to intended interaction count

### M6 - Runs Explorer and Run Detail

Scope:
- Advanced run filters and URL-first state
- Tabbed Run Detail: overview, games, evaluation, analysis, config, raw
- Inline replay in games tab
- Actions: clone, rerun, export, evaluate now

Exit gate:
- Run detail becomes one-stop analysis surface

### M7 - Compare Workbench (`/compare`)

Scope:
- Multi-run compare selection
- Metric table with directional deltas
- Comparative charts
- Config diff view

Exit gate:
- Compare is first-class and deep-linkable

### M8 - Settings and Notifications Hardening

Scope:
- Provider and stockfish readiness UX
- Preferences persistence behavior stabilization
- Sidebar active job badge and panel
- Toast logic for key state transitions

Exit gate:
- Observability and defaults are robust in day-to-day use

### M9 - Cutover and Legacy Cleanup

Scope:
- Activate full legacy redirects
- Remove deprecated nav paths from primary UX
- Final accessibility/perf/error-boundary hardening
- Final documentation updates

Exit gate:
- V2 UX is default, with no critical regressions

## 7. API Contract Plan (Additive)

Planned additions:
1. `GET /api/dashboard/kpis`
2. `GET /api/runs` query extensions:
   - text, evaluation state, provider/model, date range, sort, pagination
3. Run metadata extensions:
   - inferred model label
   - inferred template
   - inferred evaluation helper fields
4. `GET /api/jobs/{job_id}/moves` (SSE) for live quick-play board updates

Compatibility:
- Existing endpoints and current payload fields remain valid.

## 8. Test Matrix by Milestone

Required per milestone:
1. Backend route tests for all new/extended contracts
2. Frontend unit/integration tests for changed pages/hooks/stores
3. No broken existing smoke tests

Required E2E coverage by mid/late milestones:
1. Quick Play full flow
2. Lab launch -> monitor -> evaluated run
3. Run Detail tab flow + replay
4. Compare flow
5. Legacy route redirect flow

## 9. Documentation Revalidation Checklist

Before closing each milestone:
1. Re-open corresponding Opus sections for that milestone scope
2. Verify no drift against locked decisions
3. Record any accepted deviation in this document under "Deviation Log"

## 10. Deviation Log

None yet.

## 11. Commit Convention

Commit prefix by milestone:
- `M0:`
- `M1:`
- `M2:`
- `M3:`
- `M4:`
- `M5:`
- `M6:`
- `M7:`
- `M8:`
- `M9:`

Examples:
- `M1: introduce app shell v2 and global ui stores`
- `M4: add quick play page with auto-eval override wiring`

## 12. Next Action

Start M1 implementation:
- establish AppShell V2 skeleton
- introduce base stores and tokenized styling surface
- keep current pages reachable while migration begins
