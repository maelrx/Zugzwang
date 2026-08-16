---
name: bootstrap-workspace
description: Scaffold the Zugzwang uv monorepo after the blocking human gates are ratified. Use for M0 workspace creation, package boundaries, tooling, lockfile, and the first fake-only vertical slice.
---

# Bootstrap workspace

## Preconditions

- `GATE-001`, `GATE-002` and `GATE-004` are `accepted` in `docs/decisions/DECISIONS.yaml`.
- ADR-003, ADR-004 and ADR-005 reflect those decisions.
- Work order names allowed paths and M0 acceptance criteria.

Stop immediately if a precondition is false. Prepare a decision packet instead of selecting a default.

## Read

- root `AGENTS.md`;
- `docs/roadmap/M0-CONSTITUTION.md`;
- `docs/architecture/REPOSITORY_LAYOUT.md`;
- `docs/architecture/DEPENDENCY_RULES.md`;
- ADR-001 through ADR-010;
- scaffold templates.

## Workflow

1. Resolve package topology from the accepted gate and ADRs.
2. Create root `pyproject.toml`, `uv.lock`, package metadata and optional dependency groups.
3. Configure lint, typing, pytest, coverage and architecture tests.
4. Preserve the physical boundaries documented under `packages/` and `plugins/`.
5. Generate strict protocol models and JSON Schemas from code; compare against draft schemas.
6. Add deterministic fake backend, fake environment and fake evaluator.
7. Implement only enough application/CLI flow to validate, resolve, plan and run one fake step.
8. Run offline checks from a clean environment.
9. Update README commands, changelog, requirements traceability and M0 status.

## Required evidence

- exact commands and outputs;
- package dependency graph;
- generated schema diff;
- clean-install result;
- architecture test result;
- fake run artifact and canonical hash.

## Forbidden

- real provider calls;
- Stockfish integration;
- Web/API/UI;
- inventing a package split different from accepted ADRs;
- committing secrets or generated paid outputs;
- adding dependencies without rationale.

## Handoff

Report gates used, files created, lockfile hash, tests, unresolved boundary questions and the next backlog issue.
