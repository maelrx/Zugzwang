---
id: ADR-050
title: "Lease formal capabilities by decision phase"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD section 9"
---

# ADR-050: Capability leases

Strategies receive a frozen `DecisionCapabilities` value and a bound gateway.
Phase A of reason-first search has no enumeration lease. Phase B receives it
only after the free-reasoning call.

The lease is a small typed object rather than a dependency-injection registry.
That keeps navigation cost low and makes forbidden operations fail closed.
