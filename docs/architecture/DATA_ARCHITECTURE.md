# Arquitetura de dados

## 1. Three-plane model

### Operational database

SQLite stores mutable projections and coordination state.

Suggested tables:

```text
schema_migrations
experiments
runs
conditions
episodes
steps
attempts
model_calls
tool_invocations
events
artifacts
metric_observations
budget_ledger
checkpoints
plugin_snapshots
```

### Content-addressed artifact store

```text
.zugzwang/objects/sha256/ab/cd/<digest>
```

Objects include prompts, raw responses, images, traces, rendered boards, engine transcripts, resolved manifests and reports.

### Analytical plane

Parquet tables optimized for scans:

- runs;
- conditions;
- episodes;
- steps;
- attempts;
- calls;
- metrics;
- costs;
- protocol violations.

DuckDB queries these without a server.

## 2. SQLite policy

- WAL mode;
- foreign keys on;
- busy timeout;
- short transactions;
- no network filesystem;
- one logical writer;
- explicit checkpoint policy;
- runtime version check.

SQLite’s official WAL documentation records a rare WAL-reset corruption bug affecting older versions under concurrent connections and checkpoints. The doctor command must accept only a fixed runtime, recommended 3.51.3+ or current 3.53.x, with documented official backports when necessary.

Reference: [SQLite WAL](https://www.sqlite.org/wal.html).

## 3. Artifact transaction protocol

1. stream bytes to temp file;
2. calculate SHA-256 and size;
3. fsync when policy requires;
4. atomic rename into CAS;
5. begin DB transaction;
6. insert or reuse artifact row;
7. append events;
8. update projection;
9. commit.

Orphaned CAS objects are safe and collectible. DB references to missing objects are integrity errors.

## 4. Retention

Artifact metadata is always retained. Payload policy may be:

- full;
- redacted;
- encrypted;
- hash-only;
- omitted due provider/legal policy.

The bundle records which policy applied to each artifact class.

## 5. Schema migration

Alembic migrations are forward-only during pre-1.0 development. Downgrade may exist for local convenience but is not the recovery strategy. Backup and compatibility fixtures precede migration.

## 6. Export

Parquet schema has its own version. Export is deterministic in field meaning, not necessarily byte-identical across library versions unless canonical writer settings are fixed.

## 7. Garbage collection

GC is mark-and-sweep:

- roots: active DB refs, pinned bundles, imported evidence;
- grace period;
- dry-run report;
- never delete unknown files;
- audit event for deletion.

## 8. Postgres trigger

Adopt Postgres only when measured requirements include multiple writer processes/hosts, remote workers, tenancy, network storage, or query contention that SQLite cannot meet.

## 9. Research evidence projections

Migration `0003` adds direct step and attempt references for observation,
decision trace, wire request, wire response and reasoning telemetry artifacts.
It also adds `evaluation_runs`, so metric rows identify the exact post-hoc
generation that produced them.

Migration `0004` adds `search_sessions`, `search_nodes`, `search_edges` and
`search_retrieval_events`. Migration `0005` records whether declared
assistance was exceeded at run, episode and step level. Migration `0006` stores
the effective H/K string on each committed step.

The graph and provider payloads remain in CAS. SQLite stores references and
indexed metadata only.
