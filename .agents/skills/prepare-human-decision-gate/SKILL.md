---
name: prepare-human-decision-gate
description: Prepare a concise but complete evidence packet for a pending Mestre Mael decision without selecting or implementing the decision on the operator’s behalf.
---

# Prepare human decision gate

## Workflow

1. Read gate, linked ADR, affected requirements/roadmap and current code state.
2. Verify primary technical/legal/provider sources.
3. List viable options and status quo.
4. Quantify implementation, adoption, compatibility, scientific and operational impacts where possible.
5. Identify irreversible or expensive consequences.
6. State recommendation, assumptions and confidence.
7. Produce smallest prototype/benchmark that reduces uncertainty, if allowed.
8. Fill a Decision Record with `selected_option: null`.
9. Name exact milestones/files blocked.
10. Stop and request human signature.

## Output style

Lead with the actual fork and recommendation. Include a decision table, not a cloud of abstractions. Never modify `selected_option`, `approved_by` or ADR status.
