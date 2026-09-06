---
id: ADR-055
title: "Represent model-only search as an immutable DAG"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 23-27"
---

# ADR-055: SearchWorkspace immutable DAG

Search branches are nodes and edges produced by model actions and formal
transitions. `PositionKey` supports transposition lookup. `TrajectoryKey`
preserves repetition-sensitive causality. Search never mutates the canonical
game state.

The initial implementation is local and bounded. It does not introduce a
distributed graph service.
