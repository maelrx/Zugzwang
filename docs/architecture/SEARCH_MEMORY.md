# Search memory

Search Memory is endogenous. It contains only material generated during the
current model-only search: candidate notes, refutations, formal verdicts,
branch summaries, failures and transposition references.

It is not RAG and it is not a chess database. The first implementation uses an
in-memory list behind a retriever protocol. The same records can later be
projected into SQLite and FTS5 without changing the decision contract.

The deterministic retrievers are exact state, ancestors, siblings, root move,
refutation, failure, frontier, disagreement and transposition. Each result
keeps source node IDs and the model that generated it.

The fabric rejects Stockfish, tablebase and `evaluation://` content. Derived
summaries never replace their source notes.

The R7 ablation has two explicit modes. Episodic mode constructs an empty
fabric for every turn. Persistent mode seeds the new turn from the latest
committed search graph in the same episode and keeps the source position keys
needed for exact-state retrieval after the workspace root changes. It never
crosses episode or run boundaries.
