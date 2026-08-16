# Política de claims e evidência

## Vocabulário obrigatório

### Demonstra

Resultado diretamente observado sob protocolo publicado, com artifacts e uncertainty adequados.

### Sustenta

Múltiplas evidências convergentes dentro de regimes claramente delimitados.

### Sugere

Inferência plausível, mas com explicações alternativas abertas.

### Não estabelece

Alegação que excede o desenho, a métrica ou a distribuição.

## Claims proibidos sem evidência adicional

- “o modelo entende xadrez” a partir de puzzles IID;
- “nível mestre” a partir de rating interno;
- “reasoning fiel” a partir de resposta correta;
- “multimodal reasoning” quando FEN também estava presente e não houve attribution probe;
- “RAG melhora” quando o retrieved example contém transposição/target leakage;
- “LLM jogou” quando engine escolheu ou ranqueou o move;
- “reproduzível” sem bundle, hashes, exact configuration e caveat de provider mutável;
- “mais barato” sem incluir retries e failed calls;
- “sem search” quando labels foram produzidos por search, salvo formulação correta de inference-only.

## Evidence ladder

1. numerous public audited games;
2. controlled paired engine matches;
3. local decision sets with strong post-hoc evaluation;
4. hidden or temporal puzzles;
5. human move prediction;
6. state/legal metrics;
7. qualitative examples.

As camadas respondem perguntas distintas. Nenhuma substitui todas as outras.

## Minimum publishable record

- exact model/provider/date;
- full source and resolved manifests;
- code/plugin/schema versions;
- prompts and content hashes;
- raw response or documented retention restriction;
- retry/pass@k/selector;
- tools and assistance;
- engine and budget;
- seeds/temperature;
- costs/tokens/latency;
- parsing vs illegal vs strategic error;
- sample provenance;
- uncertainty;
- known threats;
- statement of what the experiment does not establish.

## Explanation policy

Explanations are decomposed when possible into claims:

- board fact;
- legal fact;
- attack relation;
- tactical consequence;
- strategic recommendation;
- line/evaluation;
- uncertainty.

Claims should be checked by rules, line execution, engine, expert gold, or counterfactual test. LLM-as-judge can be secondary, never the sole factual authority.

## Attribution policy

The effective system identity includes:

```text
model
+ provider adapter
+ prompt/observation
+ knowledge packet
+ strategy
+ tools
+ retry/selection
+ environment
+ evaluator
+ budget
```

A gain belongs to the smallest supported composite, not automatically to model weights.

## Negative results

Negative and null findings are first-class. The repository should preserve:

- conditions that failed;
- false starts;
- invalid hypotheses;
- unexpected cost regressions;
- provider capability mismatches.

Deleting them creates a biased engineering memory.
