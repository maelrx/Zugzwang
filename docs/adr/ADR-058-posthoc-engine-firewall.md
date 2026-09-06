---
id: ADR-058
title: "Keep post-hoc engine artifacts outside live search"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 31-32"
---

# ADR-058: Post-hoc engine firewall

The evaluator runs after a committed move and writes under the evaluation
generation. Search has no evaluator read method and rejects engine-looking
agents and references.

The same Stockfish binary may play an explicitly assisted opponent or evaluate
a run, but those are different plugins, namespaces and protocol conditions.
