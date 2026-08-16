---
name: implement-evaluator-metric
description: Implement a deterministic evaluator or versioned metric with complete provenance, cache identity, slices, uncertainty inputs, and no live-decision leakage.
---

# Implement evaluator or metric

## Workflow

1. State exactly which construct the metric measures: protocol, state, policy, value, trajectory, explanation, cost or human alignment.
2. Define inputs, exclusions, units, aggregation and missingness.
3. Assign stable metric ID and semantic version.
4. Record evaluator software/version/config/budget and dataset slice.
5. Keep post-hoc evaluator outside live decision path unless regime declares assistance.
6. Define cache key over all outcome-relevant inputs.
7. Add fixtures for normal, mate, illegal, missing and extreme cases.
8. Test deterministic recomputation from bundle.
9. Add uncertainty-compatible raw observations; do not persist only aggregate.
10. Document invalid comparisons.

## Chess-specific cautions

- ACPL depends on engine, budget and mate normalization;
- top-1 punishes equivalent moves;
- legal rate measures rules/interface, not strength;
- Elo/Glicko belongs to a pool/protocol;
- human move matching is not optimality;
- LLM-as-judge is not the sole fact verifier.
