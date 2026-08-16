# Desenho experimental e estatística

## 1. Princípio central

A posição-base é a unidade de comparação. Condições devem ser aplicadas aos mesmos estados sempre que possível. Isso reduz variância e torna pequenas baterias mais informativas que torneios soltos.

## 2. Preregistration mínima

Cada experiment card congela:

- pergunta;
- hipótese principal;
- conditions;
- primary outcome;
- exclusions;
- sample construction;
- provider/model snapshots;
- token/call/cost budget;
- retry policy;
- engine evaluator;
- statistical estimator;
- multiplicity policy;
- promotion criterion.

Mudanças posteriores são amendments datados.

## 3. Sampling

### Stratification

Amostras devem cobrir:

- phase;
- tacticality;
- branching factor;
- material;
- side to move;
- opening familiarity;
- result balance;
- check status;
- rule edge cases.

### Grouping

Variantes da mesma posição ou transformação pertencem ao mesmo group. Split e bootstrap respeitam o group.

### Temporal control

Quando possível, usar posições posteriores ao cutoff conhecido do modelo ou derivadas de partidas recentes, sem afirmar ausência absoluta de contaminação.

### Cheap controls

Incluir:

- random legal;
- frequency/opening baseline;
- nearest-neighbor baseline;
- small specialized policy where available.

## 4. Randomização

- randomizar ordem de conditions por position/model;
- randomizar label opaco das legal actions;
- balancear side-to-move;
- separar seed do environment e seed do provider;
- registrar quando provider ignora seed;
- não reusar stochastic samples como se fossem independentes.

## 5. Outcomes

### 5.1 WDL loss

Preferível para agregar posições com escalas diferentes e evitar explosão de centipawns perto de mate.

### 5.2 Centipawn loss

Reportar com:

- engine/version;
- depth or time;
- mate normalization;
- clipping/winsorization rule;
- phase slices.

### 5.3 Accuracy

Top-1 é útil, mas trata alternativas quase equivalentes como erro. Sempre combinar com ranking/value loss.

### 5.4 State metrics

- exact FEN components;
- piece-square accuracy;
- castling/en passant accuracy;
- legal affordance distance.

### 5.5 Protocol metrics

- parse first pass;
- legal first pass;
- final valid;
- retry count;
- fallback;
- timeout;
- protocol violation.

## 6. Estimadores recomendados

### Paired effect

Para cada posição:

\[
d_i = y_{i,A} - y_{i,B}
\]

Reportar média/mediana pareada, intervalo bootstrap clusterizado e distribuição dos sinais.

### Cluster bootstrap

Resamplear position families, não respostas individuais.

### Hierarchical model opcional

Quando houver múltiplos modelos, positions e repeats:

```text
outcome ~ condition
        + phase
        + condition:phase
        + (1 | position_family)
        + (1 | model_snapshot)
```

Não tornar Bayesian/hierarchical modeling requisito do runtime. Ele pertence ao reporter/analysis layer.

### Full games

Bootstrap por opening pair. Para engine testing posterior, SPRT pode ser usado se hipóteses, bounds e stopping rule forem preregistrados.

## 7. Multiplicidade

- uma hipótese primária por experiment;
- outcomes secundários marcados;
- Benjamini-Hochberg para famílias exploratórias quando apropriado;
- não escolher a melhor slice após ver os dados e chamá-la de primary;
- publicar todas as conditions executadas.

## 8. Missingness and failures

Failures são outcomes:

- timeout;
- provider refusal;
- malformed output;
- image unsupported;
- invalid tool call;
- budget exhaustion.

Não imputar um move de fallback no score do modelo sem reportar o fallback como componente distinto. Um forfeiture policy deve ser explícito.

## 9. Repeated stochastic calls

Para temperature > 0:

- `attempt_id` único;
- mesma condição pode ter replicates;
- pass@k separado de pass@1;
- selector identificado;
- cost multiplied;
- dependence within position acknowledged.

## 10. Power

Antes de gastar em APIs:

1. executar fake and local controls;
2. fazer pilot pequeno;
3. estimar variance pareada;
4. simular power para effect sizes relevantes;
5. definir stop for futility;
6. travar budget.

O objetivo não é maximizar N, mas comprar informação.

## 11. Promotion funnel

```text
schema validation
→ fake provider
→ local/open model smoke
→ paid provider pilot
→ held-out replication
→ full local-decision suite
→ full-game promotion
```

## 12. Report card

Todo relatório deve declarar:

- claim supported;
- claim not established;
- sample and exclusions;
- effect and interval;
- cost;
- protocol deviations;
- data and model cutoff caveats;
- H/K/R/O/B/D profile;
- source and resolved manifest hashes.
