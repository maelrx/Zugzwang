# Política de migrations e upcasters

## Database migrations

- Alembic owns operational schema history;
- migration is forward-tested from every supported release fixture;
- destructive change uses expand/migrate/contract when data matters;
- migration does not make provider calls or depend on network;
- downgrade support is documented, not presumed;
- backup/rollback command is part of release notes.

## Protocol upcasters

Persisted events and bundles are immutable evidence. New readers may upcast old representations in memory, but never rewrite the original artifact silently.

```text
v1 raw event → verified upcaster → current in-memory event
```

Every upcaster has:

- source and target schema versions;
- pure deterministic transform;
- golden before/after fixture;
- lossiness flag;
- provenance in imported projection.

## Breaking changes

A breaking protocol change requires ADR, major schema version and compatibility statement. Pre-1.0 is not permission to corrupt or reinterpret prior evidence.
