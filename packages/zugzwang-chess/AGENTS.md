# AGENTS.md: zugzwang-chess

## Responsibility

Standard-chess environment, codecs, renderers, tasks, opponents and rules-library adapter.

## Dependency policy

Allowed: zugzwang-core environment contracts plus accepted rules/rendering substrate.

Forbidden: Runtime DB access, provider SDKs, CLI commands, live strategic engine evaluation in environment.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M2`; do not pull later milestone features forward.
