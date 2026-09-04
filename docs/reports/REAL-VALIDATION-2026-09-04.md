# Real validation, 4 September 2026

This report covers the current code after the evidence, legality gateway,
search, evaluator and R5 review changes. The model and the engine runs below
used real local services. Unit tests use fakes only where the test must be
offline.

## Runtime used

- provider path: `provider.openai_compatible` through the local OpenCode router;
- router: `http://127.0.0.1:8788/v1`;
- model: `muse-spark-1.3-contributor-free`;
- engine: Stockfish 16;
- engine SHA-256: `00628bd9c9855c1b7ff93d7f8d51b413586cdc6336fe637f9a14a61531a05aca`;
- opponent bucket: requested Elo 1000, represented as the documented
  approximation `UCI_Elo=1320` plus `Skill Level=0`;
- post-hoc evaluator: evaluator version `0.3.0`, Stockfish maximum skill,
  20,000 nodes, `MultiPV=3`, `UCI_ShowWDL=true`, one thread.
- R5 test model: `muse-spark-1.3-contributor` through the OpenCode Go pool;
  the free-pool attempt remains a separate, rate-limited condition.

The configured MuseSpark path is the OpenAI-compatible adapter above. A
temporary native OpenCode daemon was started for one adapter probe. With the
default catalog it did not contain MuseSpark; with an ephemeral model entry it
reached MuseSpark but sent Chat Completions, which the router rejected because
this model requires Responses. The temporary daemon was stopped; the
persistent 8788 router was left active. The successful MuseSpark runs below
therefore use the configured real router path, not a fake provider.

## Real runs

| Run | Condition | Result | Evidence |
|---|---|---|---|
| `run_OIX5_WunD9U3PYB-1cqTVw` | one-move smoke, no transport retry | failed on real `429` | failure is preserved in SQLite and events |
| `run_2BpC3AXFABUDoc_ujijy7w` | one-move smoke, five transport retries | completed | 1 provider call, 96 input and 41 output tokens, wire request/response and telemetry |
| `run_8p4bsDXxAUsUuKirrbxzbg` | MuseSpark vs Stockfish approximate 1000, 8 plies | completed | 4 MuseSpark moves, 4 completed and 1 failed provider attempt, real engine opponent |
| `run_15iqHfrm3zlNAoROIz2q6g` | MuseSpark vs Stockfish approximate 1000, no ply limit | completed by formal mate | 38 plies, 19 MuseSpark moves, 21 completed provider attempts, all 21 wire/telemetry-complete |
| `run_1hT5UmCrkHwTE_0JGVD7IQ` | MuseSpark vs Stockfish approximate 1000, no ply limit, final-path rerun | completed by formal mate | 100 plies, 50 MuseSpark moves, 91 provider attempts, all 91 wire-complete, 56 provider-exposed telemetry artifacts; evaluation `eval_PcJo7CYUsmYAWGTS72pv7g` |
| `run_flif7pmlu-v7KDTyV4O8Hg` | real R6-BatchedTree | completed | 3 model candidates, 3 formal transitions, 3 Search Memory retrievals, 4 completed and 1 failed provider attempt |
| `run_b8OvWcrEMFYDn0F4FGrChg` | real R6-BatchedTree with AdversarialRefuter | completed | 1 candidate, 1 refutation, 1 Search Memory retrieval, two completed MuseSpark calls |
| `run_qwq1oGKrcaGMh6o7dNVcXQ` | real MuseSpark self-play, 8 plies | completed | 8/8 steps have observation and decision trace refs; 13 provider attempts, 8 telemetry artifacts |
| `run_ivNACcDMIGXuQjXpuedgPg` | real R2 binary repair | completed | no legal list in observation, one MuseSpark decision, evaluation `eval_6kFQyZsjsYy7CL-CCttrcw` |
| `run_24xC9zH12tP3_0FWE1Kzlg` | R5 multi-agent review, MuseSpark vs Stockfish | blocked by real upstream limit | first model decision persisted Critical Scout → Strategic Planner → Final Reviewer, 11 provider attempts all returned 429; no fake fallback |
| `run_MJbLjAATctvMff_-0X60yQ` | R5 multi-agent review, MuseSpark Go vs Stockfish approximate 1000 | completed | 8 plies, 4 model decisions, 12/12 provider attempts completed, 3 roles per decision, real post-hoc evaluation `eval_TSCXYxgxM0AUWUiu9XrSOA` |
| `run_9FDUejOJmPHoZVM1z5z3dw` | R5 multi-agent review, MuseSpark Go vs Stockfish approximate 1000, no ply cap | completed by formal mate | 56 plies, 28 model decisions, 84 logical calls, 93 completed provider attempts, real post-hoc evaluation `eval_Ot6mR6tPmdcWRZ2Pe25wkQ` |

The R7 legal-tree persistent-memory full game is
run_kYRs9O0z2yB8ZrQobZefww. It used MuseSpark Contributor 1.3 with reasoning
low and output ceiling 16384, the real OpenCode-compatible router, and real
Stockfish approximate 1000. It completed 48 plies with 24 model turns, 72
completed provider attempts, 24 SearchWorkspaces, 216 retrieval events and
formal checkmate by 24...Qxg2#. Post-hoc evaluation is
eval_7JbW2q2r-SwMSlAy8kYmtQ.

The real strategy matrix also completed all five conditions. The matrix kept
the same MuseSpark model and position. Its effective assistance was H2 for
`direct`, H3 for `grounded` and `reason_then_ground`, and H2 for `repair` and
`structured`.

| Strategy | Run | Completed provider attempts | Provider tokens in/out |
|---|---|---:|---:|
| `chess.direct` | `run_pBAC3aWArXJDWe17a_bO8g` | 1 | 96 / 37 |
| `chess.grounded` | `run_8z5PE4jYCSvBbSR0BZOdKA` | 1 | 189 / 44 |
| `chess.reason_then_ground` | `run_ziH4iROVK29h--u3r8PPtw` | 2 | 463 / 484 |
| `chess.repair` | `run_-84zI_GTrtICZqg-BmmODg` | 2 | 77 / 125 |
| `chess.structured` | `run_xKBmAo95rAFdz_LbYEhtcw` | 5 | 98 / 227 |

The long game ended with the formal final FEN
`r5nr/pppk2pp/3pp3/8/6n1/2P5/P1P3RP/R1Bq2K1 w - - 4 20` after
`...f3d1`, a checkmate for Black. The workspace did not stop on a ply cap.

## Post-hoc Stockfish results

The latest evaluation generations are:

- full game: `eval_kdFEPUXkoAdp62_BPnRtxQ`;
- final-path full game: `eval_PcJo7CYUsmYAWGTS72pv7g`;
- R5 Go multi-agent review: `eval_TSCXYxgxM0AUWUiu9XrSOA`;
- short game: `eval_KNDC6EB58dGjDZtaIaiyEg`;
- R6 current refuter path: `eval_SHas-l8yfukcEXhhJrx3lQ`;
- R0 one-move smoke: `eval_CQ3NmGomjIK2IBJCZ9Cb1g`;
- R2 one-move condition: `eval_6kFQyZsjsYy7CL-CCttrcw`.

The long game produced 238 metric observations over 19 MuseSpark moves. The
18 moves with centipawn-to-centipawn comparison had:

- mean CPL: `95.222`;
- median CPL: `27`;
- maximum CPL: `614`;
- WDL loss mean: `0.040`;
- best-move agreement: `10/19` (`0.526`);
- classes: 11 best/good, 2 blunders, 3 mistakes, 2 inaccuracies and 1 move
  whose mate transition had no CPL value;
- one explicit `mate_after` observation.

The short real game had mean CPL `10`, WDL loss mean `0.058`, and best-move
agreement `0.75` over four model moves.

The current R6 real move selected `e2e4` after one model-generated refutation
`e7e5`. Its maximum-strength evaluation was CPL `5`, WDL loss `0.011`, chosen
rank `1`, and Stockfish also selected `e2e4`. This is one move, not an Elo
claim. The earlier R6 probe remains in the database as a separate run.

R0 and R2 both selected `e2e4` in their one-position real probes and both
measured CPL `5` under the same Stockfish evaluation configuration. The sample
is too small to compare strategies statistically. The protocol distinction is
still real: R2 had no legal list in its observation and declared binary repair.

The R5 run was intentionally not scored as a game: the OpenCode router returned
`FreeUsageLimitError` for every transport attempt before the first model move.
Its durable trace still proves that the three logical roles were instantiated
in order, with three call records, no legal-action enumeration and no engine
input. A successful R5 game needs a later free-tier window; switching to a
different model would create another condition, not a continuation of this one.

The Go-pool R5 run completed the same chain with the free model substitution
explicitly recorded in its manifest. It produced the sequence
`e2e4 e7e5 Nf3 d5 exd5 Ne7 d6 cxd6` over 8 plies. All four model turns have
three logical calls and the role order is present in every DecisionTrace. The
provider reported `5,522` input and `6,588` output tokens. Post-hoc Stockfish
gave the four model moves mean CPL `39`, median `17`, maximum `122`, WDL loss
mean `0.255`, and best-move agreement `1/4`; classes were 3 best/good and 1
mistake. This is a small integration test, not a strength claim.

The no-cap Go R5 game completed at 56 plies with `...Rd1#` and final FEN
`1k6/p6p/1p4p1/8/8/5P2/PPP2PRb/K2r4 w - - 2 29`. It produced 352 metric
observations over 28 model moves. The 27 centipawn comparisons had mean CPL
`75.111`, median `31`, maximum `591`; WDL loss mean was `0.063`, best-move
agreement `0.357`, and chosen rank mean `1.278` over 18 ranked observations.
The move classes were 16 best/good, 6 mistakes, 4 inaccuracies, 1 blunder and
1 explicit mate transition. The provider reported `60,426` input and `82,329`
output tokens. This is a single full-game integration result, not an Elo claim.

Mate scores are stored as mate metrics. The evaluator does not turn mate into
an arbitrary centipawn value.

The final-path full game produced 609 metric observations over 50 MuseSpark
moves. Its 44 centipawn-to-centipawn comparisons had mean CPL `197.909`,
median CPL `58`, and maximum CPL `2369`; WDL loss mean was `0.071`. Best-move
agreement was `0.260` over 50 observations, with 22 best/good, 10 mistakes, 7
inaccuracies, 5 blunders and 6 explicit mate/no-CPL observations. MultiPV rank
was available for 26 observations, with mean chosen rank `1.308`. This run
ended after 100 plies with formal checkmate by `...Ra2#` and final FEN
`5rk1/1n2b3/4p3/7p/1n1P1p2/6P1/r2K4/q7 w - - 4 51`.

## Evidence checks

The real long-game databases contain direct references for every provider
attempt's canonical request, lowered wire request, normalized response and
reasoning telemetry. In the final-path run, all 91 provider attempts have
wire request/response refs; 56 completed attempts also have provider-exposed
telemetry. The provider exposed reasoning-token counts and encrypted reasoning
items. The kernel stores those fields as provider telemetry; it does not call
them private chain-of-thought.

The real R6 database contains `search://` nodes and edges only. Its search
session is `ses_R0xQMQS0xDRMt5t70W2uiA`. No Stockfish artifact or
`evaluation://` reference can be inserted into the SearchWorkspace or Search
Memory.

The R5 failure trace is `sha256:623e23a92417ff4353fb8173873a2162855c1214901e874b9561cafa12e4690e`.
It records the role order `critical_scout`, `strategy_planner`,
`final_reviewer`, three logical calls and `engine_used=false`; the eleven
transport attempts and their 429 wire responses remain separate attempts.

The successful Go R5 run has 4 decision traces, 12 direct provider attempts,
12 wire request/response pairs and 12 provider-exposed telemetry artifacts.
The trace IDs retain the final reviewer attempt selected from each three-call
chain; no engine or legal-action enumeration appears in the live rationale.
Its bundle is `/tmp/zugzwang-real-go-multi-agent-review-bundle-20260904`;
all 82 checksum entries verified successfully.

The no-cap Go R5 run has 28 decision traces, exactly 3 calls per trace, 93
completed provider attempts, 93 wire request/response pairs and 93
provider-exposed telemetry artifacts. Its exported bundle is
`/tmp/zugzwang-real-go-multi-agent-review-full-bundle-20260904`; all 584
checksum entries verified successfully.

`zugzwang trace step STEP_ID` reads the live decision and selected evaluation
generation without executing either provider or engine.

## Offline gates

The final offline suite passed `228` tests, skipped `1` architecture test and
deselected `6` opt-in tests. Ruff and Pyright strict both passed with zero
errors. The JSON schemas were regenerated from the Pydantic contracts.

The final-path run was exported to
`/tmp/zugzwang-real-current-bundle-20260904`. Its 493 checksum entries
(489 CAS artifacts plus four top-level files) all verified successfully; the
bundle is 4.5 MiB and declares the resolved manifest, raw wire, observations,
decision traces, reasoning telemetry and evaluation generation complete.

The full ten-run battery ZIP made before this foundation work is kept as a
historical artifact. These real-run IDs are the post-change validation set.
