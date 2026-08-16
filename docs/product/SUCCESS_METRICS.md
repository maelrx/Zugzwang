# Métricas de sucesso

## Não usar como north star

- estrelas no GitHub isoladamente;
- número de providers cadastrados;
- quantidade de jogos executados;
- um Elo máximo sem protocolo;
- tamanho do bundle;
- número de features;
- volume de tokens consumidos.

## Métricas de adoção científica

1. Número de bundles públicos válidos.
2. Número de reproduções independentes.
3. Proporção de resultados com source e resolved manifests.
4. Número de papers, posts técnicos ou benchmarks que reutilizam schemas.
5. Quantidade de plugins externos que passam contract tests sem patches no core.
6. Tempo mediano para reproduzir uma condição existente.
7. Percentual de bundles importáveis e reavaliáveis em releases posteriores.

## Métricas de integridade

1. Protocol violation detection rate em fixtures adversariais.
2. Cobertura de attempts, retries, tool calls e costs no event stream.
3. Porcentagem de claims que publicam uncertainty.
4. Taxa de resultados que separam H/K regimes.
5. Zero ações ilegais aplicadas ao ambiente canônico.
6. Zero secrets em bundles de fixtures.
7. Zero fallback ou routing não declarado.

## Métricas de engenharia

- tempo do smoke suite offline;
- tempo de resume após crash;
- tamanho de instalação mínima;
- throughput de event persistence;
- peak memory em suites locais;
- compatibility fixture pass rate;
- schema backward-read success;
- wheel coverage após eventual extensão Rust.

## Gate de valor do v0.1

O v0.1 tem valor real quando:

- REP-001, GROUND-001 e SKILL-001 podem ser executados com fake e um provider real;
- bundles são importados em outra máquina;
- todos os artifacts e metrics são ligados a provenance;
- a mesma análise pode ser refeita offline;
- um reviewer consegue explicar exatamente o que mudou entre duas condições.
