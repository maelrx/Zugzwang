---
name: write-or-update-adr
description: Create, amend, supersede, or ratify an Architecture Decision Record with alternatives, direct/indirect impacts, reversibility, evidence, owner, and human gate linkage.
---

# Write or update ADR

## Workflow

1. Confirm the matter is architectural rather than a local code detail.
2. Assign next stable ADR ID and copy `ADR-TEMPLATE.md`.
3. Describe context and forces without smuggling the preferred answer into the problem.
4. List realistic alternatives, including status quo.
5. Analyze direct, indirect, objective and subjective impacts inside and outside the project.
6. State decision, constraints, exceptions and rejected shortcuts.
7. Record reversibility, migration and revisit trigger.
8. Link requirements, risks, gates and sources.
9. If human-owned, keep `status: proposed` until signed in DECISIONS.yaml.
10. Update ADR index and superseded records.

## Never

- retroactively edit an accepted ADR to pretend history was different;
- mark recommendation as acceptance;
- omit license/privacy/scientific attribution impacts;
- use “industry standard” as sole evidence.
