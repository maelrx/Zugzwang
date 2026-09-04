---
id: ADR-051
title: "Persist observation and decision evidence per step"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 13-16"
---

# ADR-051: Decision evidence model

Every model step writes an observation artifact and a decision-trace artifact.
SQLite stores direct references; CAS stores the immutable JSON. Attempts keep
direct links to their provider artifacts.

The old event traversal remains available for compatibility. Direct columns
make audit and UI queries fast without making events non-canonical.
