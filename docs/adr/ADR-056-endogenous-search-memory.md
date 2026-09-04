---
id: ADR-056
title: "Keep search memory endogenous and namespace-isolated"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 28-33"
---

# ADR-056: Endogenous Search Memory

Search Memory contains only model-generated notes and formal search results
from the current workspace. It uses a small in-memory facade first. Retrieval
results retain source node IDs and generator identity.

Stockfish, tablebases, external databases and `evaluation://` references are
rejected. FTS5 or semantic retrieval can be added later without changing the
pure-search namespace.
