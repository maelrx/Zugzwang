# Planejamento de custo e sensibilidade estatística

## Two-stage execution

1. **Pilot:** estimate failure rate, paired variance, latency and real token distribution.
2. **Confirmatory:** freeze sample size and budget using pilot estimates without optimizing toward a favorable effect.

## Cost projection

For condition `c`:

\[
C_c = N_c \left(E[n_{calls}] C_{call} + E[t_{in}] C_{in} + E[t_{out}] C_{out}\right)
\]

The registry must distinguish provider-reported usage, estimated usage, cached tokens, subscription/flat-plan cost and marginal API price. A dollar estimate without pricing snapshot receives `cost_status=estimated` or `unknown`.

## Sensitivity, not magical power

Before variance is known, report the minimum paired effect detectable under plausible standard deviations rather than inventing precise power. After pilot:

- use PositionFamily cluster as unit;
- account for repeated models/conditions;
- inflate for provider failure/missingness;
- reserve budget for preregistered rerun policy, not opportunistic retries;
- do not stop because the p-value or leaderboard looks attractive.

## Budget gates

```yaml
budget_approval:
  gate: GATE-011
  pilot_usd: null
  confirmatory_usd: null
  contingency_percent: null
  hard_stop: true
  approved_by: null
```

Paid execution is impossible while `approved_by` is null.
