# Legality gateway

The chess environment owns the rules. The `LegalityGateway` owns exposure.

`StandardChessRulesKernel` can parse actions, validate them, enumerate legal
actions, apply a transition and detect terminal states. It never ranks a move.
The runtime binds a phase-specific capability lease before calling a strategy.

The lease can allow:

- binary validation, which returns only `{"legal": true|false}`;
- a reason category, such as `ILLEGAL_KING_EXPOSED`;
- an enumerated legal-action set, classified as H3;
- hypothetical transitions, which return a child state and terminal status.

The environment does not materialize a delayed legal-action set in the initial
observation. A reason-first strategy asks the gateway for that set only after
its analysis call completes.

Every query increments a manifest-controlled budget and emits a gateway event.
The query itself carries an assistance impact. The run's effective assistance
is the maximum impact observed, not the declared value.

Binary repair never includes a move count, legal-action list, ranking or engine
signal. The enumerated profile is explicit and is H3 even if an old manifest
called it `legality_only`.
