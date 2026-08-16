---
name: build-run-bundle
description: Implement, validate, import, redact, or evolve the self-contained run bundle and its checksummed evidence/analytical artifacts.
---

# Build run bundle

## Invariants

- original evidence is immutable;
- every referenced artifact exists and hashes correctly;
- source and resolved manifests are both present;
- code/plugin/provider/evaluator/pricing snapshots are explicit;
- public derivative cannot masquerade as full private bundle;
- import does not execute arbitrary code or trust paths.

## Workflow

1. Enumerate required files from `RUN_BUNDLE_SPEC.md`.
2. Generate deterministic relative paths and manifest.
3. Normalize timestamps only where protocol allows; do not rewrite event time.
4. Copy/link CAS objects safely and reject path traversal/symlink surprises.
5. Emit analytical Parquet from frozen projections.
6. Produce `checksums.sha256` and validate before finalization.
7. Import into fresh workspace without provider/engine.
8. Recompute reference projections/metrics offline.
9. Derive redacted/public bundle through a documented transform and new identity.
10. Test schema/upcaster compatibility against old fixture corpus.
