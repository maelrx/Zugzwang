# Search workspace

`SearchWorkspace` is a bounded hypothetical graph. It receives a trusted
rules kernel and one root state. It never receives Stockfish data.

Nodes contain a state reference, `PositionKey`, `TrajectoryKey`, parent,
depth, root action and model provenance. Edges record every proposed action,
including illegal proposals that were rejected without creating a child.

`PositionKey` supports transposition lookup. `TrajectoryKey` keeps causal
history separate, which matters for repetition-sensitive chess states.

The root and each branch state are immutable from the workspace's point of
view. Only the rules kernel creates a resulting state. Search budgets cover
nodes, validation queries, transition queries and depth.

The graph is projected into `search_sessions`, `search_nodes`,
`search_edges` and `search_retrieval_events`. The complete graph is also kept
as a CAS artifact with the `search://` namespace.

The workspace rejects engine-looking agents and `evaluation://` references.
That check is a second line of defense; the live search API has no evaluator
repository dependency.

R7 uses the same workspace once per model decision. The mapper's root
candidates and the variant analyst's replies become legal or rejected edges;
the gateway is rebound to each legal child to expose its finite reply set, and
the final reviewer receives the resulting branch summaries. The graph is not a
Git worktree: it is a bounded, immutable state DAG owned by the experiment.
