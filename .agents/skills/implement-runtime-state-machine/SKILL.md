---
name: implement-runtime-state-machine
description: Implement run, episode, step, attempt, cancellation, checkpoint, budget, or resume behavior in the durable local runtime.
---

# Implement runtime state machine

## Invariants

- committed actions are never repeated;
- attempts are append-only;
- event and projection advance atomically;
- finalization is idempotent;
- ambiguous provider outcomes remain ambiguous;
- cancellation is structured and diagnostic;
- no external call occurs inside a database transaction.

## Workflow

1. Draw the transition table and list terminal/non-terminal states.
2. Define command preconditions and emitted events.
3. Implement reducer/domain transition separately from I/O.
4. Implement repository/application orchestration through ports.
5. Add injected failure points before and after each boundary.
6. Test interruption at every transition edge.
7. Test resume from every persisted non-terminal state.
8. Verify budget reservations/releases and duplicate command behavior.
9. Record event schema or migration impact.
10. Run replay test against golden event stream.

## Required tests

- exhaustive transition test;
- illegal transition rejection;
- cancellation during provider call;
- crash before/after CAS and SQL commit;
- duplicate finalize;
- outcome_unknown timeout;
- hard budget stop;
- resume without duplicate action.

Do not “repair” a corrupt state by deleting evidence. Surface a diagnostic failure and preserve artifacts.
