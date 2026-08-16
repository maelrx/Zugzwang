# AGENTS.md: provider-pydantic-ai

## Responsibility

ModelBackend adapter using Pydantic AI Direct requests as low-level transport/schema substrate.

## Dependency policy

Allowed: Public provider contract and pinned Pydantic AI integration APIs.

Forbidden: Pydantic AI Agent semantics, hidden retries/tools/memory/fallback.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M3`; do not pull later milestone features forward.
