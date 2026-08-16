---
name: database-migration
description: Create or review an operational SQLite migration and any related event/bundle upcaster with interruption, compatibility, and evidence-preservation tests.
---

# Database migration

## Workflow

1. Add fixture from the oldest supported schema.
2. Specify data volume, lock and rollback expectations.
3. Prefer additive expand/backfill/contract sequence.
4. Keep migration deterministic and offline.
5. Never alter immutable raw evidence to fit new semantics.
6. Add repository/projection changes.
7. Test fresh install, upgrade, interrupted upgrade and repeated upgrade.
8. Add upcaster when protocol representation changed.
9. Update compatibility matrix and release notes.
10. Run bundle import/replay from pre-migration fixture.
