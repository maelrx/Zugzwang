---
id: ADR-045
title: "Topologia de publicação dos packages"
status: proposed
decision_owner: "Mestre Mael"
human_gate: GATE-012
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-045: Topologia de publicação dos packages

## Contexto

ADR-006 define fronteiras físicas internas, mas não decide se cada package vira uma distribuição PyPI independente. A publicação afeta installation UX, version coupling, dependency solving, plugin authoring, release automation e capacidade de consumir somente `core`.

## Opções

### A. Uma distribuição agregadora, packages internos separados

O source conserva boundaries, mas o usuário instala um pacote principal.

- **Direto:** instalação e documentação mais simples; release único.
- **Indireto:** consumidores não instalam `core` isoladamente sem carregar extras/metadados do agregador.
- **Externo:** menor atrito para adoção inicial e tutoriais.
- **Subjetivo:** parece produto coerente, não coleção prematura de bibliotecas.

### B. Uma distribuição por package

`zugzwang-core`, `zugzwang-runtime`, `zugzwang-chess`, `zugzwang-cli` e plugins versionados separadamente.

- **Direto:** dependências mínimas e integração granular.
- **Indireto:** release choreography, compatibility matrix e resolver mais complexos.
- **Externo:** melhor para embedders avançados; pior para primeira instalação.
- **Subjetivo:** transmite modularidade, mas pode parecer fragmentação artificial.

### C. Um único package físico

Todos os módulos vivem em uma distribuição e árvore única.

- **Direto:** scaffold e release mínimos.
- **Indireto:** boundaries dependem mais de disciplina e architecture tests.
- **Externo:** UX simples, plugin authors recebem superfície maior.
- **Subjetivo:** risco de monólito sem módulos apesar do desenho.

## Recomendação

Começar com packages físicos no monorepo e uma distribuição agregadora no primeiro release. Publicar subpackages separadamente apenas quando existir consumidor real que justifique compatibilidade independente.

## Consequências

- GATE-012 precisa ser ratificado antes do primeiro PyPI release;
- package metadata e lockfile não devem prometer topology pública antes disso;
- API boundaries continuam testadas independentemente da distribuição.

## Reversibilidade

Média. Separar distributions depois é possível; recombinar ecossistema já publicado é mais custoso.

## Reavaliar

Quando houver plugin externo, pedido concreto por `core` standalone ou custo mensurável de dependências agregadas.
