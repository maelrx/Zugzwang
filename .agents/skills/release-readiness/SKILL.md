---
name: release-readiness
description: Audit and prepare a Zugzwang foundation, alpha, or scientific release across gates, tests, migrations, bundles, licensing, SBOM, documentation, compatibility, and claims.
---

# Release readiness

## Workflow

1. Identify release class and its criteria.
2. Verify all blocking human gates and accepted ADRs.
3. Build from clean checkout with locked dependencies.
4. Run full offline test suite and clean-install smoke test.
5. Validate schemas, migrations, upcasters and old bundles.
6. Generate SBOM, checksums and artifact inventory.
7. Verify license notices and third-party obligations.
8. Verify no secrets/private provider outputs leak.
9. For scientific release, run claims/evidence and assistance audits.
10. Produce signed-off readiness report with blockers and residual risk.

A release candidate with an unresolved blocker remains a candidate. Do not downgrade the blocker by wording.
