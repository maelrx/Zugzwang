---
id: ADR-052
title: "Retain lowered provider wire payloads separately"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-005 for public export
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 18-19"
---

# ADR-052: Raw wire retention

Adapters return the payload immediately before transport and the response
before normalization when the provider makes them available. Canonical and
normalized artifacts stay separate. Credential-shaped fields are redacted
before CAS storage.

OpenCode currently reports `PARTIAL` fidelity. Public redistribution remains
blocked by GATE-005. Local private retention is the selected operating mode.
