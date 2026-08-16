---
name: test-fault-replay
description: Design and execute fault-injection, interruption, idempotency, migration, or replay tests for the runtime, persistence, provider and bundle boundaries.
---

# Test fault and replay behavior

## Workflow

1. List side-effect boundaries and commit points.
2. Add deterministic fault hooks before/after each boundary.
3. Execute crash/cancel/timeout at each hook.
4. Restart from persisted workspace.
5. Verify state machine, evidence completeness and no duplicate committed action.
6. Compare event/projection checksums against expected fixture.
7. Test duplicate command and finalize idempotency.
8. Test migration/upcaster before replay when relevant.
9. Test missing/corrupt artifact behavior without silently healing evidence.
10. Record operational envelope and untested fault classes.

## Boundaries to prioritize

- CAS temp/write/rename;
- SQL transaction commit;
- provider request send/response receive;
- UCI process start/read/timeout;
- Parquet/bundle finalization;
- signal cancellation;
- budget reservation/release.
