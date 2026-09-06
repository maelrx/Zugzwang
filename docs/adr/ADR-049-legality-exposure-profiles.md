---
id: ADR-049
title: "Make legality exposure profiles explicit"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 7 and 11"
---

# ADR-049: Legality exposure profiles

Retry profiles are `no_retry`, `parse_only`, `binary_legality`,
`legality_reason` and `enumerate_after_failure`. The old `legality_only` value
maps to binary feedback for compatibility. Enumeration is always recorded as
H3.

This makes an experimental condition identifiable from its actual interface.
The migration accepts old manifests and the resolver records the new profile.
The choice is reversible while v1alpha1 remains private.
