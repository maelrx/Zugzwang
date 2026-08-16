# CI e quality gates

## Pull request pipeline

1. Foundation/document validator.
2. Formatting and lint.
3. Static typing.
4. Unit/property tests.
5. Architecture boundary tests.
6. Contract tests with fakes.
7. SQLite/CAS integration tests.
8. Migration/upcaster fixtures.
9. Security and secret scan.
10. Build package and validate wheel metadata.
11. Generate JSON Schemas and fail on uncommitted drift.
12. Example manifests dry-run.

## Scheduled pipeline

- dependency/security audit;
- compatibility against newest allowed Python and SQLite;
- provider golden-fixture drift review, without paid calls by default;
- docs/link audit;
- performance trend benchmarks;
- bundle backward compatibility corpus.

## Manual paid pipeline

Requires:

```yaml
provider_e2e:
  approved_by: Mestre Mael
  max_total_usd: ...
  models: [...]
  artifacts_policy: ...
```

The job hard-stops when the approved budget is exhausted. Its results do not gate ordinary code PRs because provider availability is external.

## Merge gates

- no unresolved critical review;
- no pending human gate that the PR assumes;
- schema/migration compatibility acknowledged;
- risk register updated when exposure changes;
- test evidence attached;
- code owner review for `core`, migrations, protocol schemas and security.
