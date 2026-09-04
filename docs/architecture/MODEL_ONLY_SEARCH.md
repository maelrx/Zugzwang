# Model-only search

The first R6 strategy is `chess.r6_batched_tree`.

It asks the model for a small candidate set, validates every candidate with the
rules kernel, prunes illegal branches, then asks the same model to compare the
remaining hypothetical positions. Several blind judge calls are aggregated by
majority. The aggregation code has no chess facts.

The strategy records candidate provenance, rejected edges, judge calls, votes,
selected root action, search budgets and whether an engine was available. It
does not use Stockfish, an opening book, tablebases or external retrieval.

`R6-BatchedTree` is intentionally smaller than MCTS. It provides a legible
first experiment. Interactive expansion, adversarial refutation and adaptive
branching can build on the same workspace once its evidence is trusted.
