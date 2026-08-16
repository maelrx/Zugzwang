# AGENTS.md: reporter-parquet

## Responsibility

Analytical Parquet exports and reference DuckDB queries from stable projections.

## Dependency policy

Allowed: Public report/metric contracts, Arrow/Parquet/DuckDB dependencies.

Forbidden: Mutating operational DB/evidence, defining canonical runtime semantics.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M4`; do not pull later milestone features forward.
