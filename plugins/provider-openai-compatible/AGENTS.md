# AGENTS.md: provider-openai-compatible

## Responsibility

Direct HTTP adapter for explicit OpenAI-compatible dialects and local inference servers.

## Dependency policy

Allowed: Public provider contract and HTTP client.

Forbidden: Assuming dialect equivalence, hidden model routing, silent field dropping.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M3`; do not pull later milestone features forward.
