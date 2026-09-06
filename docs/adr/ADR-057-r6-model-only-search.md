---
id: ADR-057
title: "Start R6 with BatchedTree and blind model judges"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0079 / PRD sections 34-41"
---

# ADR-057: R6 model-only search

`chess.r6_batched_tree` asks the model for candidates, validates them formally,
and uses the same model to compare legal hypothetical positions. Majority vote
selects the root action. The aggregate has no chess-specific score.

This is easier to audit than starting with MCTS. Adversarial roles and adaptive
branching can extend the same trace once this path is stable.
