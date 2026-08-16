# Governança da documentação

## Canonical locations

| Subject | Source of truth |
|---|---|
| Product boundary | `docs/product/` |
| Scientific claims | `docs/research/` |
| Architecture | `docs/architecture/` + accepted ADRs |
| Requirements | `docs/requirements/` |
| Wire contracts | `docs/protocol/` + `schemas/` |
| Delivery sequence | `docs/roadmap/` |
| Human decisions | `docs/decisions/DECISIONS.yaml` |
| Agent instructions | root/nested `AGENTS.md` + `.agents/skills/` |

## Change rules

- ADR wins over older narrative architecture text; both must be reconciled in same PR.
- Machine-readable schema wins over example when they conflict; conflict is a bug.
- Requirement ID is never reused.
- Research claim includes source, protocol scope and evidence tier.
- External update after dossier cutoff is labeled with date and primary source.
- Translations identify canonical language and last synchronized commit.

## Review ownership

- scientific docs: research auditor;
- protocols/schemas: core maintainer;
- security/privacy: security owner;
- ADR/gates: Mestre Mael for human-owned items;
- README/positioning: product maintainer plus technical reviewer.

## Staleness

Each release performs a docs review. A document that is intentionally historical moves to `archive/`; it is not left in canonical paths with stale instructions.
