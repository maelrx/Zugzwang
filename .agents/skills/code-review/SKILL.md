---
name: code-review
description: Perform an independent, defect-first review of a Zugzwang change covering correctness, architecture, scientific integrity, persistence, security, tests, migrations, and documentation.
---

# Code review

## Method

1. Read work order and acceptance criteria.
2. Inspect diff and surrounding code, not only PR description.
3. Reconstruct behavior and side effects.
4. Run or inspect the relevant tests.
5. Seek counterexamples: cancellation, duplicate, unknown, malformed, unsupported, old-version and budget-boundary cases.
6. Check package dependencies and public API delta.
7. Check H/K attribution, retries and metric provenance.
8. Check secret/raw artifact handling and path/process safety.
9. Check migrations/upcasters and old fixtures.
10. Report findings ordered by severity with file/line, impact and suggested correction.

Do not bury a correctness/security finding beneath style comments. If no findings remain, state residual risks and test limitations.
