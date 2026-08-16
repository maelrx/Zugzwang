# Catálogo de experimentos v0.1

**Status:** proposta científica para preregistration  
**Escopo:** inferência, sem fine-tuning  
**Unidade inicial:** decisões locais pareadas  
**Engine:** somente avaliação pós-hoc, salvo positive controls explicitamente separados  
**Objetivo:** produzir sinais causais baratos antes de promover condições para partidas completas

## 0. Constituição experimental comum

### 0.1 Pergunta do programa

Quanto da competência observada pode ser extraída ou destruída alterando apenas:

- representação do estado;
- momento do action grounding;
- conhecimento externo estático;
- redundância ou conflito entre modalidades;
- seleção de demonstrações;

mantendo provider, modelo, posição, budget e evaluator controlados?

### 0.2 Suite comum

A suite inicial deve conter posições distribuídas por:

- opening, middlegame e endgame;
- táticas e posições quietas;
- branching factor baixo, médio e alto;
- checks, evasões e threats;
- pawn structures recorrentes;
- posições sem nome de abertura recuperável;
- regras raras em slice separado;
- temporal holdout;
- random-legal OOD;
- transformações geométricas em subset.

A unidade de split é a posição-base ou a família metamórfica, nunca uma variante textual individual.

### 0.3 Tasks mínimas

Cada condição pode executar uma ou mais tasks:

1. `StateReconstruction`
2. `LegalActionGeneration`
3. `MoveSelection`
4. `CandidateRanking`
5. `ClaimVerification`
6. `FullGame`, apenas após promoção

### 0.4 Outcomes primários

- parse success;
- exact or partial state reconstruction;
- affordance distance;
- legal action rate;
- normalized WDL loss;
- clipped centipawn loss;
- top-k engine rank;
- tactical solution pass@1 when applicable;
- cost, tokens, latency;
- declared/effective H and K;
- protocol violations.

### 0.5 Regras gerais

- comparar condições dentro da mesma posição;
- alternar ordem de apresentação;
- fixar ou registrar seed quando suportado;
- manter output schema e token budget constantes;
- contabilizar retries como novas attempts;
- não excluir failures silenciosamente;
- aplicar avaliação pós-hoc idêntica;
- preregistrar outcome primário;
- publicar effect sizes e uncertainty;
- separar análise exploratória.

---

# REP-001: Representation Matrix

## Pergunta

Como FEN, ASCII, PGN/histórico, imagem e combinações redundantes afetam perception, tracking e decisão local em modelos multimodais e text-only?

## Hipóteses

- `H1`: FEN supera imagem isolada em state exactness para modelos gerais.
- `H2`: PGN beneficia modelos com forte familiaridade de pretraining, mas degrada com história longa.
- `H3`: FEN + imagem pode superar FEN em posições geometricamente complexas, mesmo sem adicionar informação de estado.
- `H4`: ganhos de representação não são uniformes por fase ou branching factor.
- `H5`: a melhor condição para legalidade pode não ser a melhor para WDL loss.

## Condições mínimas

| ID | Estado | História | Modalidade |
|---|---|---|---|
| `REP-A` | FEN | nenhuma | texto |
| `REP-B` | ASCII | nenhuma | texto |
| `REP-C` | nenhuma | PGN completo | texto |
| `REP-D` | board image | nenhuma | imagem |
| `REP-E` | FEN + ASCII | nenhuma | texto redundante |
| `REP-F` | FEN + image | nenhuma | multimodal redundante |
| `REP-G` | FEN | últimos 8 plies UCI | texto |
| `REP-H` | FEN | PGN completo | texto |
| `REP-I` | image | últimos 8 plies | multimodal |
| `REP-J` | FEN + image | últimos 8 plies | multimodal redundante |

A bateria 80/20 pública pode começar com `A`, `C`, `D` e `F`.

## Controles

- orientação fixa na primeira análise;
- imagens renderizadas da mesma fonte canônica;
- sem legal moves no primary arm;
- mesma instrução lógica, adaptada apenas ao formato;
- sem nomes de abertura;
- output UCI estruturado;
- nenhum retry sem arm separado.

## Subtasks

Em subset balanceado:

1. pedir estado estruturado;
2. pedir legal affordances;
3. pedir ação;
4. pedir claims objetivos sobre ataques e checks.

Isso permite identificar se a imagem foi percebida ou ignorada.

## Métricas

### Primária

Normalized WDL loss por posição.

### Secundárias

- state exactness;
- piece-square F1;
- legal move rate;
- top-1/top-3;
- CP loss clipped;
- token/latency/cost;
- interaction com phase, tacticality e branching factor.

## Análise

Modelo de comparação pareada por posição. Reportar:

- median paired difference;
- cluster bootstrap por position family;
- heterogeneous effects;
- Pareto front qualidade-custo;
- proportion of positions in which each representation wins.

## Critério de promoção

Uma condição entra em full-game se:

- melhora o outcome primário com intervalo útil;
- não degrada legalidade ou cost de forma desproporcional;
- efeito aparece em mais de uma slice;
- artifact/render reproducibility passa.

## Riscos

- contaminação de PGN;
- provider redimensionar imagem silenciosamente;
- FEN e image não serem token/cost-comparáveis;
- modelo ignorar uma modalidade;
- SAN/PGN carregar leakage não presente em UCI.

---

# GROUND-001: Reason First, Constrain Later

## Pergunta

Legal moves mostrados desde o início melhoram apenas validade ou também policy? Forçar análise antes do grounding preserva deliberação e remove ilegalidade no momento da escolha?

## Hipóteses

- `H1`: legal-first eleva validade e reduz variance.
- `H2`: reason-first/legal-later produz menor WDL loss que legal-first em modelos de reasoning.
- `H3`: tool on-demand gera uso adaptativo correlacionado à complexidade.
- `H4`: opaque indices reduzem semantic leakage da lista legal.
- `H5`: constrained decoding mede ranking, mas não rule knowledge.

## Condições

| ID | Descrição | H class |
|---|---|---|
| `G0` | geração livre UCI | H2 |
| `G1` | geração livre SAN | H2 |
| `G2` | legal UCI desde o início | H3 |
| `G3` | legal SAN desde o início | H3 |
| `G4` | análise sem lista, depois legal UCI e escolha | H3 |
| `G5` | análise sem lista, tool `legal_moves()` sob demanda | H3 quando usada |
| `G6` | análise e action mask/opaque indices no commit | H3 |
| `G7` | legal actions por índices opacos desde o início | H3 |

Primary 80/20: `G0`, `G2`, `G4`, `G7`.

## Separação de attempts

- parse repair;
- illegal repair;
- strategic rethink;
- second sample.

Somente os dois primeiros pertencem a R2. Um “tente de novo e jogue melhor” é outra strategy.

## Metrics

- first-attempt parse/legal rate;
- final legal rate;
- WDL/CP loss first attempt;
- WDL/CP loss committed action;
- tokens before legal list exposure;
- legal tool invocation rate;
- reasoning length and candidate diversity as descriptive metrics;
- cost per valid action;
- delta between intended and committed candidate.

## Leakage audit

SAN legal lists podem revelar:

- checks/mates;
- captures;
- piece identity;
- ambiguity;
- castling.

O primary comparison deve usar UCI ou opaque indices. SAN é uma ablação própria.

## Promotion gate

Promover `G4` se dominar `G2` na fronteira qualidade-custo e mantiver final legal rate dentro de tolerância. Promover `G5` somente se tool behavior for estável e auditável.

---

# SKILL-001: Causal Expert Knowledge Injection

## Pergunta

Um general-purpose LLM usa conhecimento enxadrístico modular de forma causal durante decisão, ou apenas responde ao priming de “texto de expert”?

## Unidade

`KnowledgePacket`, não Codex agent skill e não RAG.

## Hipóteses

- `H1`: packet correto melhora posições correspondentes.
- `H2`: persona “GM” tem efeito menor que conteúdo correto.
- `H3`: packet errado plausível degrada decisões nas features às quais se refere.
- `H4`: packet irrelevante token-pareado não reproduz o ganho.
- `H5`: efeito é maior em posições quietas/estratégicas que em táticas forçadas.
- `H6`: modelo pode verbalizar o packet sem usá-lo na ação, portanto explanation similarity não é outcome primário.

## Condições

| ID | Knowledge class | Conteúdo |
|---|---:|---|
| `S0` | K0 | baseline |
| `S1` | K1 | “Você é um GM” |
| `S2` | K2 | princípios genéricos |
| `S3` | K3 | checklist correto da fase |
| `S4` | K4 | packet correto da estrutura/abertura |
| `S5` | K4 | packet plausível de outra estrutura |
| `S6` | K2/K4 placebo | texto irrelevante token-pareado |
| `S7` | K4 adversarial | packet sutilmente incorreto |
| `S8` | K5 | exemplo expert semanticamente pareado |
| `S9` | K7 | análise current-position derivada de engine, positive control separado |

O headline científico deve comparar `S0`, `S1`, `S4`, `S5`, `S6`, `S7`.

## Construção dos packets

Cada packet declara:

- domínio e scope;
- factual claims;
- applicable features;
- contraindications;
- token count;
- source/provenance;
- license;
- curator;
- prohibited leakage;
- expected direction of effect.

Packets não podem conter o target move ou uma transposição próxima do item de avaliação em `S4`.

## Matching

Uma posição só recebe `S4` quando um matcher determinístico confirma features relevantes. O matcher faz parte do dataset construction, não da inferência. A posição recebe `S5` de uma estrutura semanticamente plausível, mas incompatível.

## Outcomes

### Primária

Interaction:

\[
(\text{S4}-\text{S0}) - (\text{S5}-\text{S0})
\]

em normalized WDL loss.

### Secundárias

- adherence to packet recommendations;
- move-category changes;
- claim factuality;
- susceptibility to false packet;
- confidence calibration;
- cost and token overhead.

## Causal interpretation

`S4 > S0` isoladamente é insuficiente. Pode refletir maior esforço. A evidência mais forte é:

```text
correct packet > persona ≈ irrelevant packet
correct packet > wrong packet
subtle false packet changes decisions in predicted direction
```

## Safety and integrity

- packets são data, nunca system instructions executáveis;
- nenhum packet pode instruir tool use ou modificar protocol;
- content hash entra no condition identity;
- source licensing é obrigatório;
- engine-derived packets são `K7`, não “expert knowledge genérico”.

## Promotion gate

Promover packet injection para partidas se o efeito for:

- conteúdo-específico;
- estável em held-out positions;
- resistente a token-matched placebo;
- não dependente de uma única opening family;
- economicamente defensável.

---

# MM-001: Symbolic and Visual Redundancy

## Pergunta

Uma imagem redundante melhora a decisão quando o modelo já recebe um estado simbólico exato?

## Condições

| ID | Input |
|---|---|
| `M0` | FEN |
| `M1` | RGB |
| `M2` | FEN + RGB |
| `M3` | PGN |
| `M4` | PGN + RGB |
| `M5` | FEN + PGN |
| `M6` | FEN + PGN + RGB |

Primary: `M0`, `M1`, `M2`.

## Hipóteses

- `H1`: `M2 > M0` em relações geométricas complexas, sugerindo scaffold espacial.
- `H2`: `M2 = M0` quando o modelo ignora visão.
- `H3`: imagem aumenta custo e latency mais que qualidade para algumas famílias.
- `H4`: benefício depende de renderer, orientation e model profile.

## Attribution probe

Em alguns items, perguntas auxiliares exigem:

- localizar peças;
- identificar attacks;
- reconhecer pinned pieces;
- enumerar checks.

Se `M2` melhora move selection sem melhorar qualquer probe visual, a interpretação espacial deve permanecer cautelosa.

## Visual nuisance matrix

Em secondary experiment:

- board theme;
- piece set;
- coordinates;
- resolution;
- orientation.

O estado simbólico permanece idêntico. Isso mede brittleness a features irrelevantes.

## Promotion gate

Somente promover multimodal redundancy se:

- efeito positivo sobre qualidade;
- efeito não explicado por accidental prompt differences;
- robustez a pelo menos dois renderers;
- provider request artifact registra exact image bytes.

---

# MM-002: Cross-Modal Conflict and Source Authority

## Pergunta

Quando fontes de estado discordam, qual modalidade o modelo privilegia e a instrução de autoridade consegue governar essa escolha?

## Condições base

- consistent FEN A + image A;
- FEN A + image B with one-piece displacement;
- side-to-move conflict;
- orientation conflict;
- textual auxiliary claim conflict.

## Authority arms

| ID | Instrução |
|---|---|
| `C0` | nenhuma fonte declarada |
| `C1` | FEN autoritativo |
| `C2` | imagem autoritativa |
| `C3` | detectar e reportar conflito, sem escolher |
| `C4` | tool canônica resolve conflito |

## Tasks

1. source conflict detection;
2. piece location;
3. attack relation;
4. legal actions;
5. move selection;
6. calibrated abstention.

## Metrics

- conflict detection;
- source-follow rate;
- authority compliance;
- hallucinated reconciliation;
- abstention calibration;
- decision quality under each authoritative truth;
- modality trust matrix by model.

## Threats

- o provider pode preprocessar imagem;
- modelos podem inferir que FEN “parece mais oficial”;
- system prompt authority pode dominar sem visual understanding;
- position B precisa ser legal e matched em difficulty.

## External relevance

O mesmo padrão aparece em agentes que recebem screenshot, DOM, database state e natural-language instruction. Chess fornece ground truth exato para estudar source trust.

---

# DEMO-001: Relevant Few-Shot versus Random Many-Shot

## Pergunta

A seleção semântica de poucas demonstrações importa mais que volume bruto de context examples?

## Motivação

LMAct encontrou pouco ganho ao aumentar massivamente demonstrações expert em chess. Isso não resolve se a falha foi quantidade, seleção, formato ou token density.

## Condições token-pareadas

| ID | Demos |
|---|---|
| `D0` | zero-shot |
| `D1` | 3 aleatórias |
| `D2` | 3 da mesma opening family |
| `D3` | 3 da mesma pawn structure |
| `D4` | 3 do mesmo tactical motif |
| `D5` | 3 nearest semantic, sem transposition leakage |
| `D6` | 1 Best Line compacta |
| `D7` | 16 aleatórias truncadas ao mesmo budget |

## Retrieval constraints

`D5` é construído offline. Proibir:

- mesma posição;
- transposição;
- mesma game continuation;
- target move leakage;
- eval atual.

Registrar retrieval features e distance.

## Hypotheses

- matched structure/motif supera random;
- one dense Best Line pode superar many random examples;
- demonstrations help explanation more than policy in some models;
- excessive examples dilute current state.

## Outcomes

- WDL loss;
- candidate recall;
- demonstration-copy rate;
- exact continuation leakage checks;
- cost;
- prompt utilization diagnostics.

---

# EXT-001: Geometric and Metamorphic Stability

**Status:** P1, recomendado para entrar após o pipeline básico.

## Transformações

- mirror files;
- rotate 180 + color swap;
- notation conversion;
- coordinate relabeling;
- irrelevant theme changes;
- causal piece removal;
- threat neutralization.

## Invariants

- transformed action equivalence;
- state-answer equivalence;
- calibrated decision change under causal perturbation.

## Valor

Esse experimento se tornará a semente de ChessFuzz dentro do kernel, sem obrigar um produto separado no v0.1.

---

# FULL-001: Promotion to Full Games

Condições locais não viram claims de força automaticamente.

## Requisitos de promoção

1. effect size pré-registrado;
2. held-out replication;
3. stable protocol;
4. cost ceiling;
5. no hidden assistance;
6. paired openings;
7. colors swapped;
8. sufficient game count or sequential design;
9. phase metrics;
10. raw evidence policy satisfied.

## Opponent ladder

- random legal, apenas completion sanity;
- Maia/human policy, para estabilidade e human-like pressure;
- weak UCI engine configurations;
- stronger engine only after calibration.

## Reports

- score with intervals;
- ACPL/WDL loss by phase;
- protocol failures;
- costs and latency;
- game length;
- conversion and survival;
- opening pair bootstrap;
- exact H/K/R classification.

No single Elo is the v0.1 headline.
