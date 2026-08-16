---
name: audit-assistance-provenance
description: Audit a run, strategy, tool, dataset, prompt, or report for hidden operational assistance H, knowledge assistance K, engine leakage, retries, and attribution errors.
---

# Audit assistance and provenance

## Audit path

1. Trace every input visible before the final action.
2. Classify parser/rules/environment/legal-actions/model-only-search/engine involvement as H0-H7.
3. Classify generic/phase/opening/retrieved/current-position knowledge as K0-K7.
4. Compare declared ceiling to effective events.
5. Inspect SAN `+/#`, top-k, evaluations, PVs, candidate labels and tool outputs for leakage.
6. Inspect SDK/runtime for hidden retry, fallback, routing or cache.
7. Verify dataset/training-derived engine information is distinguished from live assistance.
8. Verify report and leaderboard names match the system, not only the base model.
9. Emit violations with evidence event/artifact IDs.
10. Block claim/publication when attribution cannot be reconstructed.

## Output

```yaml
assistance_audit:
  declared: {R: R3, H: H3, K: K4}
  effective: {R: R3, H: H5, K: K4}
  status: protocol_violation
  findings: []
```
