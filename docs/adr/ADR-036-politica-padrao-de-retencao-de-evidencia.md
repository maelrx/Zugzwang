---
id: ADR-036
title: "Política padrão de retenção de evidência"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-003
date: "2026-08-12"
accepted_date: "2026-08-16"
source: "integrated foundation design"
---

# ADR-036: Política padrão de retenção de evidência


## Contexto

Raw prompts, responses e images maximizam auditabilidade, mas podem conter dados sensíveis, outputs com restrições de redistribuição e custo de storage.

## Recomendação

Default local `full-private`, com bundle público exigindo política explícita. Secrets sempre redacted. O operador precisa ratificar se raw retention vem ligada por default.

## Opções

1. full por default;
2. metadata/hash-only por default;
3. provider-specific;
4. encrypted local full plus public redacted derivative.

## Trade-offs

Full fortalece reprodução e aumenta risco. Hash-only protege dados e enfraquece auditoria. Derivative bundles adicionam complexidade, mas separam trabalho privado de publicação.

## Impactos externos

Define confiança científica, compliance e possibilidade de compartilhar resultados.

## Reversibilidade

Muito baixa para dados não coletados: evidência omitida não pode ser recuperada.
