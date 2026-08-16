# AGENTS.md: evaluator-stockfish

## Responsibility

External UCI Stockfish supervision and post-hoc versioned chess metrics.

## Dependency policy

Allowed: Public evaluator/tool contracts, process supervisor, chess canonical types.

Forbidden: Bundled binary before gate, live advice in unassisted regime, unversioned eval defaults.

## Agent rules

- Read root `AGENTS.md` first.
- Work only under a `ZGW-XXXX` work order.
- Preserve this boundary and add architecture tests for every new dependency edge.
- Do not publish a type as public API without compatibility analysis.
- Update this README when responsibility changes through ADR.
- First implementation belongs to `M4`; do not pull later milestone features forward.
