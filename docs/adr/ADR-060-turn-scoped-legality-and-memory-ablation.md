---
id: ADR-060
title: "Expose legal moves and compare episode-scoped search memory"
status: proposed
decision_owner: "Mestre Mael"
human_gate: none
date: "2026-09-04"
source: "ZGW-0081"
---

# ADR-060: Expose legal moves and compare episode-scoped search memory

The new experimental strategy uses an explicit R7 condition. The legality
gateway enumerates the finite legal action set at the start of every model
decision and the same set is included in the mapper, variant analyst and final
reviewer contexts. Proposed root candidates and variant replies still pass
through formal validation and immutable SearchWorkspace transitions.

For every legal root branch, the same leased gateway is rebound to the
hypothetical child state and exposes the finite legal reply set to the variant
analyst and reviewer. These child action sets are recorded with count and hash
in the decision rationale; they are not a strategic ranking.

Chess does not have a finite enumerable set of all illegal strings. The
condition therefore records illegal probes proposed by the model and their
formal rejection reasons, without pretending to enumerate the complement of
the legal set.

SearchWorkspace remains per decision. Its graph is persisted as a search://
artifact. A persistent memory mode seeds the next decision from the latest
committed graph within the same episode; an episodic mode starts with no
previous-turn memory. Neither mode crosses episode or run boundaries, and
neither accepts Stockfish, tablebase or evaluation artifacts.

This is an ablation of memory availability, not a new default and not a
modification of R5. The declared coordinates are R7/H4/K0 for episodic mode
and R7/H4/K6 for persistent position-conditioned retrieval. Legal enumeration
is recorded as effective H3 and model-only branching as H4.
