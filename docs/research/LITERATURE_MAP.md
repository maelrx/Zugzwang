# Mapa da literatura e cobertura experimental

Esta tabela organiza trabalhos pelo componente que realmente testam. “Aberto” descreve disponibilidade prática reportada no dossiê, não uma auditoria jurídica.

| Trabalho | Ano | Classe | Input / interface | Intervenção | Métrica principal | O que estabelece | Lacuna para Zugzwang |
|---|---:|---|---|---|---|---|---|
| Chess Transformer | 2020 | sequence LM | PGN | pretraining | plausibilidade/jogo | LM pode modelar trajetórias | protocolo moderno e OOD |
| LM State Tracking | 2021 | world model | move history | state supervision/probes | legalidade/state | estado emerge com dados | bundle comum e multimodal |
| Maia | 2020 | human policy | board tensor/rating | behavioral cloning | human move match | imitação difere de força | adapter e métricas comuns |
| ChessGPT | 2023 | post-trained LLM | mixed chess/text | domain pretraining | task suite | linguagem + policy | full-game robusto |
| LLMs on Chessboard | 2023 | general LLM | textual boards | prompting | legalidade/qualidade | interface importa | escala e protocol contract |
| Searchless Chess | 2024 | specialized value | structured state/legal actions | 15.3B action-values | Lichess/puzzles | supervisão densa produz força | baseline importável |
| Emergent World Models | 2024 | interpretability | move sequence | probes/interventions | state/skill | representação causal parcial | standardized intervention artifacts |
| MATE | 2024 | expert reasoning SFT | candidates + explanations | strategy/tactic annotations | candidate selection | expert language ajuda reranking | inference-only skill controls |
| LMAct | 2024/25 | long-context agents | ASCII/FEN/PGN/RGB | 0–512 demos, CoT | episode reward | format and demos can be isolated | modern model replication |
| ChessLLM | 2025 | full-game SFT | long trajectories | pass@10 | engine matches | long games may help | retries and rating audit |
| Chess-R1 | 2025 | RLVR | FEN/PGN, SAN/UCI, legal moves | dense vs sparse reward | puzzle accuracy | grounding and priors matter | common harness |
| ChessArena | 2025/26 | benchmark | four modes | legal moves/reasoning | Glicko/puzzles | protocol dominates some rankings | attribution and bundles |
| LLM CHESS | 2025 | benchmark | FEN/ASCII/history/tools | interface and reasoning ablations | completion/engine rating | operational failures are central | cost-strength curves |
| MET-Bench | 2025 | multimodal tracking | text and visual changes | zero/five-shot, CoT | final state | visual tracking is distinct | chess decision integration |
| OOD Compositionality | 2025 | robustness | unusual states/Chess960 | distribution shift | legalidade/quality | rules transfer better than strategy | reproducible transform suite |
| Geometric Stability | 2025/26 | robustness | rotations/reflections | metamorphic transforms | consistency | LLM geometry is brittle | property-based framework |
| VAM | 2026 | RL exploration | textual action masks | iterative masking | puzzles/ACPL | diversity mechanism matters | inference analogue |
| C1 | 2026 | distillation + RLVR | FEN + rationale | engine/teacher | puzzle pass@1 | grounded narrow reasoning improves | full-game and fidelity |
| lang-chess | 2026 | SFT + RL | Best Move/Best Line/tree | data format | accuracy/fidelity | dense concise process beats verbose trees | inference skill density |
| VPS | 2026 | process supervision | structured reasoning | verifiable subrewards | process + accuracy | answer and process diverge | atomic claim schema |
| Pre2Post | 2026 | scaling | controlled pipeline | pretrain/SFT/RL | learning curves | prior predicts RL returns | experiment import |
| KinGPT/Brittleness | 2026 | sanity/control | narrow tasks | small matched model, verifier | validity/puzzle | distribution matching can mimic understanding | mandatory cheap controls |
| Chess-World-Model | 2026 | state tracking | real/random-legal histories | architecture/data scale | exact state | IID saturation hides OOD defects | shared suites |
| UniMaia | 2026 | language-controlled expert | prompt + frozen policy | textual control | opening/skill control | language can steer expert policy | general LLM knowledge packet test |
| Strategy Verbalization | 2026 | knowledge transfer | engine tree to language | verbalization | human/LLM utility | strategy can be compressed into NL | standardized packet contract |
| Three-Body Alignment | 2026 | rationale alignment | GM/human+engine/LLM text | reranking | semantic alignment + tactics | rationale sources differ | causal policy impact |
| ACT-Eval | 2026 | commentary verification | position + commentary | atomic verification/tools | factuality/completeness | fluency hides false claims | Claim IR and evaluator plugin |
| Otter | 2026 | human policy | history/time/clock | richer context | human move prediction | temporal context is materially useful | observation-profile experiments |

## Maturidade por área

### Relativamente madura

- formal chess environments;
- UCI engine integration;
- human move modeling;
- specialized policy/value models;
- static puzzle evaluation;
- legal-move grounding.

### Em consolidação

- foundation model full-game evaluation;
- process supervision;
- multimodal state tracking;
- OOD and metamorphic testing;
- long-context expert demonstrations;
- human-language control of expert policies.

### Lacuna estrutural

- common experiment manifest;
- portable evidence bundle;
- dual assistance provenance;
- retry and selection accounting;
- provider-agnostic capability negotiation;
- causal knowledge injection controls;
- symbolic/visual redundancy and conflict under one protocol;
- cost-strength curves with paired designs.

## Regra de uso

Nenhum número desta tabela deve ser transportado para um leaderboard comum sem reconstruir:

- dataset e split;
- model snapshot;
- interface;
- legal move policy;
- retries/pass@k;
- engine role;
- time/token budget;
- rating system;
- uncertainty.
