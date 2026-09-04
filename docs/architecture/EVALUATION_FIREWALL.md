# Evaluation firewall

Evaluation is a post-hoc operation. Stockfish receives a committed position
and move after the decision has finished. It cannot write into the live
`SearchWorkspace`, and the search APIs reject evaluation namespace references.

Each evaluation pass gets an `evaluation_run_id`, evaluator ID, evaluator
version, immutable engine metadata, status and timestamps. Metric rows point to
that generation. Reports select one generation instead of merging outputs from
different evaluator versions.

The decision record can therefore answer whether Stockfish was available before
the move and what it reported only afterwards. The engine binary, options and
analysis limit belong to the evaluation generation, not to the original run.
