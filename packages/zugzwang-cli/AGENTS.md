# AGENTS.md: zugzwang-cli

## Responsibility

Human and machine CLI adapter over application services.

## Dependency policy

Allowed: Application service public APIs, Typer after ADR ratification, presentation utilities.

Forbidden: SQL, direct filesystem persistence, domain decisions, provider calls, chess rule logic.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M0-M1`; do not pull later milestone features forward.
