# AGENTS.md: zugzwang-core

## Responsibility

Pure domain model and public contracts: IDs, manifests, events, ports, budgets, assistance, metrics and errors.

## Dependency policy

Allowed: Python stdlib and deliberately accepted lightweight type/schema dependencies at boundaries.

Forbidden: Typer, FastAPI, SQLAlchemy, provider SDKs, concrete chess libraries, filesystem/network implementations, Stockfish.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M0`; do not pull later milestone features forward.
