---
id: ADR-048
title: "Separate RulesKernel from LegalityGateway"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 6-10"
---

# ADR-048: RulesKernel versus LegalityGateway

The rules kernel remains the trusted authority for formal chess. A separate
gateway controls what a strategy can observe in each phase.

This avoids relying on a strategy removing forbidden fields from a dictionary.
The direct cost is one extra runtime object and explicit leases. The benefit is
testable exposure policy and honest assistance accounting. The migration keeps
the existing environment port and adds an adapter around it.

Revisit if a second domain needs a different formal-query model.
