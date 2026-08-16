# AGENTS.md: zugzwang-runtime

## Responsibility

Application services, durable local orchestration, state machines, repositories ports, budgets, persistence coordination and bundle assembly.

## Dependency policy

Allowed: zugzwang-core plus persistence/application dependencies approved by ADR.

Forbidden: Provider-specific semantics, concrete chess policy, UI logic, arbitrary plugin internals.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M1`; do not pull later milestone features forward.
