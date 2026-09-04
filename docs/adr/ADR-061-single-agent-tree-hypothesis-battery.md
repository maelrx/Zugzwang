---
id: ADR-061
title: "Bateria controlada de agente único com árvore legal"
status: proposed
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0082"
---

# ADR-061: Bateria controlada de agente único com árvore legal

The battery uses one model agent per decision. It receives the current legal
root-action set, position-conditioned endogenous memory, and formal summaries
of hypothetical branches. The agent returns candidates, illegal probes,
variant replies and one final move in a single structured response. The runtime
validates every proposal through the RulesKernel and persists the resulting
SearchWorkspace.

The five conditions hold constant model, provider, opening, Stockfish
opponent, reasoning effort, output ceiling and retry policy. For safe local
execution, each condition is capped at 120 plies and 600 model calls; no
aggregate token, USD or wall-time cap is set in the manifest. They vary one
search or memory factor at a time around the episodic four-root baseline. The
persistent mode remains scoped to one episode.

The legal set is finite. The illegal complement is not. The experiment records
only illegal probes proposed by the agent and their formal reasons.

The condition is R7/H4. The protocol declares K6 as the maximum retrieval
contract; effective K is recorded per condition and is K0 for the episodic
control. Stockfish remains strictly post-hoc.
