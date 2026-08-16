---
id: ADR-047
title: "Semântica oficial K0-K7 para o eixo de conhecimento (emenda ADR-034)"
status: accepted
decision_owner: "Mestre Mael (operador)"
human_gate: none
date: "2026-08-16"
accepted_date: "2026-08-16"
source: "ZGW-0074"
supersedes_note: "emenda ADR-034: substitui a semântica K0-K4 do kernel pela taxonomia K0-K7"
---

# ADR-047: Semântica oficial K0-K7

## Contexto

O enum `KClass` do kernel tinha quatro classes (K0-K4) com semântica diferente
da taxonomia documentada em `docs/research/PROTOCOL_TAXONOMY.md` §3 (K0-K7).
Os experimentos SKILL-001, DEMO-001 e os controles correta/errada/irrelevante
exigem granularidade que K0-K4 não oferece (exemplos expert vs retrieval vs
análise current-position são coisas diferentes).

## Decisão

Adotar como contrato oficial a taxonomia K0-K7 já documentada:

- K0 nenhum conhecimento externo;
- K1 instrução/persona genérica;
- K2 princípios amplos estáticos;
- K3 conhecimento por fase;
- K4 skill de domínio/estrutura (ex.: Najdorf);
- K5 exemplos expert selecionados;
- K6 retrieval condicionado à posição (sem engine live);
- K7 análise expert/engine da posição atual (PV verbalizada, eval).

`KClass` (IntEnum) ganha K5-K7; `KStr` no manifest já aceitava `K[0-7]`.
O eixo H permanece inalterado; H e K continuam independentes (ADR-034).

## Alternativas

1. Manter K0-K4 e mapear os experimentos;
2. tags livres;
3. K0-K7 oficial.

## Trade-offs

Manter K0-K4 reduz atribuição (S5 vs S7 seriam a mesma classe). Tags livres
quebram enforcement e comparação entre runs. K0-K7 é compatível com o
manifest atual e com os docs de pesquisa existentes.

## Impactos

- `KClass` de K0 a K7; effective K calculado por máximo observado;
- `KnowledgePacket.knowledge_class` valida contra K[0-7];
- packets com engine markers abaixo de K7 falham a auditoria de leakage;
- docs e reports exibem a nova semântica.

## Reversibilidade

Média-baixa: classes numéricas persistem em bundles; upcasters podem
remap se necessário antes de publicação pública.
