# M4: R3, avaliação e bundles

## Objetivo

Transformar runs em evidência científica portátil e reavaliável.

## Entregáveis

- R3 structured decision strategy;
- candidate and claim traces;
- UCI engine supervisor;
- Stockfish post-hoc evaluator;
- versioned MetricDefinition and MetricObservation;
- ACPL, legal/parse rate, rank, value loss, phase slices, cost/latency;
- Parquet analytical exports and DuckDB queries;
- full run bundle, checksums, validator, import and offline re-evaluation;
- private/public bundle derivation policy.

## Entry gates

GATE-006 e GATE-009.

## Exit gate

Uma máquina limpa valida checksums, importa bundle sem provider, reproduz projections analíticas e recalcula métricas pós-hoc com provenance nova sem alterar a evidência original.
