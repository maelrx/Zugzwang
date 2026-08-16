---
id: ADR-035
title: "KnowledgePacket estático antes de RAG"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-035: KnowledgePacket estático antes de RAG


## Contexto

SKILL-001 precisa testar conteúdo experto causalmente, mas RAG adiciona corpus, embedding, chunking, retrieval, reranking e contamination.

## Decisão

Implementar `KnowledgePacket` estático e versionado no v0.1. Position-conditioned retrieval (`K6/R7`) fica fora do núcleo inicial.

## Alternativas

1. prompt hardcoded;
2. vector DB/RAG completo;
3. packet estático;
4. nenhum conhecimento externo.

## Trade-offs

Packets permitem controles corret/wrong/placebo e token matching. Não entregam descoberta dinâmica. RAG seria poderoso e metodologicamente barulhento cedo demais.

## Impactos

- schema e CAS artifact;
- packet hash na condition identity;
- provenance/license required;
- strategy renderer versioned.

## Reversibilidade

Alta. RAG pode consumir packets/corpus depois.
