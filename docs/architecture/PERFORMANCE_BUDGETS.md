# Performance budgets

These are design targets, not fabricated benchmark results.

## Local control plane targets

- manifest validation: under 250 ms for ordinary files;
- plan expansion: under 1 s for 10,000 episodes;
- event append p95: under 20 ms excluding fsync policy;
- status query p95: under 100 ms at 1M events through projections;
- resume planning: under 5 s for a 100k-step run;
- memory: bounded by concurrency and artifact streaming, not total run size.

## Artifact policy

- stream large bodies;
- avoid loading images/responses twice;
- compress event export;
- no prompt blobs in SQLite;
- bounded persistence queue.

## Provider throughput

Per-provider concurrency and rate controls are configuration. The kernel never assumes unlimited RPM/TPM.

## Measurement

M5 introduces microbenchmarks and regression thresholds. Targets are revised only with measured evidence and an ADR or performance note.
