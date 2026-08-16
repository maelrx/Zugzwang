# Run bundle specification

## Goal

A bundle is the portable scientific product of a run.

## Layout

```text
bundle/
├── bundle.json
├── manifests/
│   ├── source.yaml
│   ├── resolved.json
│   └── patches.json
├── snapshots/
│   ├── runtime.json
│   ├── plugins.json
│   ├── pricing.json
│   └── environment.json
├── events/
│   └── events.jsonl.zst
├── artifacts/
│   └── sha256/...
├── tables/
│   ├── runs.parquet
│   ├── conditions.parquet
│   ├── episodes.parquet
│   ├── attempts.parquet
│   ├── calls.parquet
│   └── metrics.parquet
├── chess/
│   └── games.pgn
├── reports/
│   └── summary.md
└── checksums.sha256
```

## `bundle.json`

Contains:

- bundle schema version;
- bundle ID;
- run IDs;
- created timestamp;
- producer version;
- protocol fingerprints;
- retention policy summary;
- file inventory;
- compatibility requirements;
- signature metadata when used.

## Integrity

- all files listed;
- SHA-256 checksums;
- no absolute paths;
- no `..`;
- no symlink extraction;
- size and count limits during import;
- artifact paths derived from hash;
- optional detached signature later.

## Retention modes

A bundle may be:

- full evidence;
- redacted;
- encrypted evidence;
- hash-only;
- metric-only due policy.

The mode is visible and limits the strength of reproducibility claims.

## Import

1. unpack into quarantine;
2. validate path safety and limits;
3. verify checksums;
4. validate schemas;
5. verify artifact-address consistency;
6. inspect compatibility;
7. register read-only imported namespace;
8. optionally copy CAS objects.

## Re-evaluation

New metrics are stored in a derivative bundle or local namespace, preserving original event history.

Machine schema: `schemas/run-bundle.schema.json`.
