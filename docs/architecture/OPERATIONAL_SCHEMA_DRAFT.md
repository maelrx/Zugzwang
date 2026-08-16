# Draft operational schema

This is a logical draft for M1 migration design, not executable DDL. Domain/event contracts are finalized first.

## Tables

### `experiments`

Source definition identity, title, tags, source manifest artifact.

### `runs`

Run ID, lifecycle state, resolved-manifest hash/ref, protocol fingerprint, created/started/finished timestamps, budget state and code snapshot.

### `conditions`

Run-scoped expanded factor combination, deterministic condition hash, intended R/H/K and observation profile.

### `episodes`

Condition membership, suite item/family identity, seed, lifecycle and termination.

### `steps`

Episode/ordinal, lifecycle, observation ref, committed action, state-before/after refs and commit timestamp. Unique `(episode_id, ordinal)`.

### `attempts`

Step/ordinal/kind, lifecycle, parse/legal/selection result, started/finished. Append-only in semantic history.

### `model_calls`

Attempt membership, backend/model fingerprint, request/raw/normalized artifact refs, outcome class, usage, latency and idempotency metadata.

### `tool_invocations`

Attempt membership, tool/version, input/output refs, assistance impact, side effect class and outcome.

### `events`

Monotonic run sequence, event ID/type/schema version, aggregate refs, payload/ref and recorded timestamp. Unique `(run_id, sequence)`.

### `artifacts`

Digest algorithm/hash, media type, size, storage locator, retention class, encryption/redaction lineage and integrity status.

### `metric_observations`

Metric ID/version, subject, scalar/structured value, evaluator snapshot, config hash, input refs and calculated timestamp. Unique identity includes metric version/config.

### `budget_ledger`

Reservation/charge/release entries by scope, resource kind, amount/status and source attempt/call.

### `checkpoints`

Run/episode progress watermark and projection/event sequence used for resume diagnostics.

### `plugin_snapshots`

Distribution/version/entry point/API version/license/config/capability and environment fingerprint.

## Index strategy

- run lifecycle and recency;
- episode by condition/status;
- step by episode ordinal;
- attempts/calls by parent and outcome;
- events by run sequence/type;
- metric by subject/key/version;
- artifact by digest primary identity;
- budget by scope/resource/time.

Indexes are justified by query plan measurement. JSON payload is not a substitute for modeled fields used by state transitions or joins.

## Transaction boundaries

- artifact bytes become durable before SQL reference;
- event, projection and budget effects commit together;
- provider/engine calls happen outside DB transaction;
- committed step transition is unique/idempotent;
- analytical export reads a stable finalized projection snapshot.
