---
id: ADR-054
title: "Give every post-hoc evaluation pass its own generation"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 21-22"
---

# ADR-054: EvaluationRun separation

`evaluation_runs` stores the source run, evaluator identity/version, engine
metadata, configuration and status. Every metric observation points to one
evaluation generation. Reports select a generation explicitly or the latest
completed one.

Re-evaluation appends rows and never edits decision evidence.
