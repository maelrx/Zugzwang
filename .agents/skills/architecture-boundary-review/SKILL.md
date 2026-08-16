---
name: architecture-boundary-review
description: Review a change for modular-monolith dependency violations, domain leakage, plugin trust, adapter coupling, premature distribution, and future API/UI compatibility.
---

# Architecture boundary review

## Review map

- core must be framework/concrete-adapter free;
- runtime owns orchestration but not provider/chess specifics;
- chess implements environment ports;
- CLI/API are adapters only;
- plugins use public contracts and never DB sessions;
- persistence is behind repositories/artifact ports;
- analytical readers consume exports, not mutate operational state.

## Workflow

1. Produce import/dependency diff.
2. Identify new public types and side effects.
3. Check each type crossing a package boundary.
4. Check configuration ownership and lifecycle.
5. Check whether convenience dependency is defining semantics.
6. Check whether Web/remote concerns leaked into local kernel.
7. Check plugin discovery/import side effects.
8. Verify architecture tests cover the new edge.
9. Require ADR for a changed direction or package responsibility.
10. Return findings by severity with concrete path and remediation.
