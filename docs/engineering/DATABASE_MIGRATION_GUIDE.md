# Guia de implementação de migration

1. Identify requirement and ADR impact.
2. Add old-version fixture before changing schema.
3. Prefer additive columns/tables and backfill in bounded transactions.
4. Do not hold migration lock while touching CAS/network.
5. Update repository queries and projection reducers.
6. Test fresh install, upgrade, interrupted upgrade and re-run.
7. Document disk/time estimates and rollback semantics.
8. Update bundle import compatibility if persisted semantics changed.

A migration that only makes tests pass but cannot explain old evidence is incomplete.
