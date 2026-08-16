---
name: implement-decision-strategy
description: Implement an explicit R0-R7 decision strategy, candidate/critic flow, retry policy, or model-only orchestration without hiding calls or assistance.
---

# Implement decision strategy

## Contract

A strategy coordinates observation, prompts, model calls, candidates, tools, verification, selection and budget. It does not mutate canonical environment state or call Stockfish unless its regime explicitly permits it.

## Workflow

1. Assign the strategy an `R` regime and allowed `H/K` ceilings.
2. Define an explicit call graph and maximum calls/tokens/retries.
3. Specify prompts/output schemas and all selection policies.
4. Emit an attempt and provenance event for every call/tool/repair.
5. Separate transport retry, parse repair, legality repair, critique and best-of-N.
6. Ensure the final action is traceable to candidates and selector.
7. Add deterministic fake-model fixtures for every branch.
8. Test budget exhaustion and partial failure.
9. Verify effective assistance taint.
10. Document comparative interpretation and non-equivalent baselines.

## Required questions

- Who generates candidates?
- Who evaluates them?
- Is the selector blind to candidate origin?
- Are legal moves shown before or after reasoning?
- Does any text contain SAN `+/#`, engine value or PV?
- Can more calls help only through a hidden oracle?

Do not call multiple samples “search” unless the system has an explicit transition/value/selection mechanism.
