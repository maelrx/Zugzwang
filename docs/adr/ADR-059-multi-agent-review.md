---
id: ADR-059
title: "R5 multi-agent review por lance"
status: accepted
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0080 / user-requested real integration test"
---

# ADR-059: R5 multi-agent review por lance

The chess plugin may expose an experimental `chess.multi_agent_review`
strategy. For each model decision it makes three sequential calls to the same
configured model:

1. **Critical Scout** maps tactical risks, hanging pieces and candidate ideas.
2. **Strategic Planner** turns that report into a plan and a short candidate set.
3. **Final Reviewer** checks both reports against the observed position and
   returns the final UCI action.

The reports are model-generated working material, not private chain-of-thought
claims. Provider-exposed reasoning remains `ReasoningTelemetry` only. No
Stockfish, tablebase, opening book, legal-action enumeration or evaluation
artifact enters the live decision. The canonical chess environment validates
and applies the final action after the strategy returns.

The regime is `R5`, assistance remains `H2/K0`, and the three calls are
recorded as separate provider attempts inside one `DecisionTrace`. A failed
role does not silently switch provider or model; the trace records the failure
and the final action is absent unless the explicit outer retry policy runs.

This is a sequential review chain, not an independent debate benchmark. Claims
about improvement require paired conditions, fixed budgets and post-hoc
Stockfish generations; this ADR only makes the orchestration observable.
