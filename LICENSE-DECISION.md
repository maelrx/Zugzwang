# License decision — resolved

**Ratified by Mestre Mael on 2026-08-16 (GATE-001): GPL-3.0-or-later for the whole project, with `python-chess` as the chess rules substrate.**

- The `LICENSE` file at the repository root contains the GPL-3.0-or-later text.
- `python-chess` (GPL-3.0+) is a distributed dependency of `zugzwang-chess`. The kernel is published under GPL-3.0-or-later to remain compatible.
- `zugzwang-core` still contains no chess library, no provider SDK and no I/O; the concrete `python-chess` types never cross the public contracts of `zugzwang-chess` (ADR-023, dependency rule §7.1).
- Revisit before any proprietary embedding scenario or external-contribution wave: relicensing requires contributor consent (ADR-004).

## History

Option B of the original analysis was selected. See [ADR-004](docs/adr/ADR-004-licenca-e-biblioteca-de-regras.md) and [DECISIONS.yaml](docs/decisions/DECISIONS.yaml) for the record.
