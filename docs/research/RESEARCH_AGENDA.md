# Agenda científica

## A. v0.1 committed

1. Representation matrix.
2. Reason-first, constrain-later.
3. Causal knowledge packet injection.
4. Symbolic/visual redundancy.
5. Cross-modal conflict.
6. Relevant few-shot versus random many-shot.

## B. Near-term extensions

### ChessFuzz

Property-based and metamorphic generation, minimization of failure traces, rotation/color-swap invariants, rare-rule suites.

### Model-only search

Measure when generator/value correlation is sufficient for search to help.

### Cross-model decomposition

Generator A, evaluator B, blind pairwise ranking, disagreement-triggered compute.

### Atomic reasoning claims

A ChessTrace-like IR for board facts, threats, candidates, lines and evidence.

### Living temporal benchmark

New positions after model cutoffs, hidden evaluation, renewable suites.

## C. Training later

- standard RLVR environment contract;
- reward provenance;
- Best Move versus Best Line;
- state pretraining before policy;
- curriculum coverage;
- process supervision;
- action-value distillation.

Training is not part of the v0.1 kernel implementation.

## D. Human modeling

- Maia/Otter adapters;
- time and clock context;
- style distributions;
- policy versus search;
- language-controlled expert policies.

## E. Security

- parser exploitation;
- tool injection;
- state tampering;
- engine process tampering;
- bundle forgery;
- specification gaming;
- prompt/data exfiltration.

## F. Beyond chess

Only after contracts stabilize:

- gridworld reference states;
- code repair with executable tests;
- formal theorem or tool environments;
- terminal tasks with immutable state snapshots.

The criterion is verifiability, not novelty theater.
