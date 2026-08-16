# Model and provider matrix

| Condition ID | Provider | Exact model snapshot | Date window | Reasoning setting | Native image | Native schema | Usage reported | Price snapshot | Artifact policy | Status |
|---|---|---|---|---|---:|---:|---:|---|---|---|
| | | | | | | | | | | planned |

## Selection rationale

The matrix should cover capability regimes, not a popularity list. Recommended inaugural shape after GATE-011:

- two frontier APIs from different provider families;
- two open-weight/local models from different architecture/size regimes;
- deterministic fake backend;
- optional specialized chess baseline outside the LLM leaderboard.

## Comparability rules

- model snapshot and execution dates are part of the condition;
- unavailable capability causes fail/skip according to manifest, never silent emulation;
- reasoning budget differences are explicit factors;
- provider routing aliases are insufficient when the actual model cannot be identified;
- updates during a run either split the condition or invalidate comparability.
