# Taxonomia de protocolo

O Zugzwang descreve uma condição por eixos independentes. Reduzir tudo a um nome de strategy destrói atribuição.

## 1. Regime de inferência `R`

| ID | Nome | Definição | v0.1 |
|---|---|---|---:|
| `R0` | Direct | uma inferência, estado para ação | sim |
| `R1` | Grounded | estado canônico e action space fornecidos | sim |
| `R2` | Repair | retry apenas para parsing ou legalidade | sim |
| `R3` | Structured | decomposição explícita em análise, candidatos, linhas e decisão | sim |
| `R4` | Best-of-N | múltiplas propostas e seletor model-only | depois |
| `R5` | Debate | proposers independentes e árbitro | depois |
| `R6` | Tree | search model-only com transições canônicas | depois |
| `R7` | Retrieved knowledge | retrieval position-conditioned sem engine live | depois |
| `R8` | Engine critic | engine avalia candidatos durante decisão | separado |
| `R9` | Engine candidates | engine gera candidatos | separado |

`R` descreve orchestration, não assistance.

## 2. Assistência operacional/estratégica `H`

| Classe | Ajuda live | Atribuição |
|---|---|---|
| `H0` | parser/formato | modelo + parser |
| `H1` | checagem de regras | modelo + formal verifier |
| `H2` | estado e transição canônicos | policy em ambiente determinístico |
| `H3` | conjunto legal exposto ou action mask | grounded policy |
| `H4` | busca apenas com modelos | model-only system |
| `H5` | engine avalia propostas | engine-critic system |
| `H6` | engine gera top-k | engine-assisted policy |
| `H7` | engine escolhe ação | LLM como interface |

A classe efetiva é calculada pelo máximo impacto observado no event stream.

## 3. Assistência de conhecimento `K`

| Classe | Conhecimento externo | Exemplo |
|---|---|---|
| `K0` | nenhum | system prompt operacional |
| `K1` | instrução/persona genérica | “jogue como GM” |
| `K2` | princípios amplos estáticos | segurança do rei, desenvolvimento |
| `K3` | conhecimento por fase | checklist de endgame |
| `K4` | knowledge packet de domínio/estrutura | planos de IQP ou Najdorf |
| `K5` | exemplos expert selecionados | partidas ou rationales pareados |
| `K6` | retrieval condicionado à posição | busca sem engine live |
| `K7` | análise expert/engine da posição atual | PV verbalizada, current eval |

`K7` pode coexistir com `H5-H7`; os eixos não são substitutos.

## 4. Perfil de observação `O`

O perfil é um objeto estruturado, não uma escala ordinal.

```yaml
observation:
  state_sources:
    - kind: fen
      authority: canonical
    - kind: board_image
      authority: redundant
  history:
    kind: last_n_plies
    length: 8
    notation: uci
  legal_actions:
    exposure: delayed
    notation: uci
  conflict_policy:
    declared_authority: fen
```

Categorias úteis:

- symbolic current state;
- textual trajectory;
- rasterized state;
- redundant multimodal;
- conflicting multimodal;
- blindfold/history-only;
- partial observability.

## 5. Budget profile `B`

- maximum model calls;
- input/output/reasoning tokens;
- wall-clock deadline;
- provider cost ceiling;
- number of candidates;
- retries by category;
- search nodes;
- tool calls;
- engine time or depth, when applicable.

## 6. Distribution profile `D`

- human IID;
- temporal holdout;
- player-disjoint;
- opening-disjoint;
- puzzle themes;
- random-legal;
- synthetic legal;
- impossible;
- transformed/equivariant;
- Chess960;
- policy-induced full-game.

## 7. Outcome profile

No single score is canonical. A condition emits a capability vector:

```text
state_exactness
affordance_distance
parse_success
legal_action_rate
candidate_recall
top_k_agreement
centipawn_or_wdl_loss
value_calibration
trajectory_completion
phase stability
explanation factuality
counterfactual faithfulness
cost
latency
protocol adherence
```

## 8. Condition identity

A comparable condition hash includes:

- resolved manifest;
- prompt templates;
- content artifacts;
- knowledge packets;
- provider/model snapshot;
- capability resolution;
- code and plugin versions;
- metric versions;
- budget and retry policy.

Changing any of these creates a new condition identity.
