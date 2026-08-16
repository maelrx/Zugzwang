---
id: ADR-033
title: "Content parts multimodais tipados"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-033: Content parts multimodais tipados


## Contexto

Os experimentos REP-001, MM-001 e MM-002 exigem texto, estado estruturado e imagem no mesmo request. SDKs de providers representam multimodalidade de formas incompatíveis.

## Decisão

O contrato canônico usa uma union fechada e versionada de `TextPart`, `StructuredStatePart`, `ImageArtifactPart` e `ToolResultPart`. Imagens são artifacts CAS, nunca URLs remotas silenciosamente resolvidas.

## Alternativas

1. string prompt apenas;
2. tipos de Pydantic AI como contrato público;
3. tipos próprios com lowering por adapter;
4. multimodalidade adiada.

## Trade-offs

Tipos próprios criam mapping adicional, mas preservam provider independence, exact bytes e provenance. Usar tipos de SDK acelera o primeiro adapter e acopla schema persistido a uma biblioteca móvel. Adiar impediria os experimentos mais diferenciados.

## Impactos

- request artifacts distinguem canonical e lowered form;
- provider capability `image_input`;
- renderer metadata e hash;
- nenhuma conversão image-to-text sem condition explícita.

## Reversibilidade

Média. O schema público precisa de versionamento.

## Reavaliar

Quando novas modalidades exigirem content parts adicionais.
