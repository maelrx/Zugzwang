---
id: ADR-001
title: "Fronteira do produto"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-001: Fronteira do produto


**Status recomendado:** aceitar.  
**Decisão:** construir um kernel de experimentos e atribuição de competência, chess-first, não um framework universal de agentes nem uma arena de produto.

### Opções

1. Benchmark específico de xadrez.
2. Framework universal de agentes/jogos.
3. Kernel pequeno com contratos gerais e plugin de xadrez rico.

### Trade-offs

A opção 1 entrega mais rápido, mas aprisiona execução, providers e provenance dentro de conceitos de partida. A opção 2 maximiza mercado narrativo e minimiza clareza: abstrações como “environment”, “reward” e “agent” viram recipientes vazios antes de existirem consumidores. A opção 3 generaliza apenas o que o problema já demonstra: calls, attempts, events, budgets, tools, strategies, environments e evaluators.

### Impactos

- **Direto:** arquitetura exige fronteira clara `core`/`chess`.
- **Indireto:** facilita usar o kernel em outro domínio verificável no futuro sem comprometer o MVP.
- **Exterior:** posiciona o projeto como infraestrutura científica, não concorrente de Lichess ou de frameworks genéricos.
- **Subjetivo/organizacional:** reduz a tentação de anunciar uma plataforma maior que o software existente; melhora credibilidade entre pesquisadores.

### Reversibilidade

Alta se o domínio vazar para o core. Baixa se contracts forem pequenos.

### Reavaliar quando

Um segundo environment real precisar do kernel e revelar abstrações ausentes.

---
