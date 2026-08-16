---
id: ADR-027
title: "Eventos próprios, logs JSON e OTel opcional"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-027: Eventos próprios, logs JSON e OTel opcional


**Status recomendado:** aceitar.  
**Decisão:** não usar observability vendor como database científica.

### Opções

1. prints/logs.
2. Logfire obrigatório.
3. OTel como tudo.
4. event store + optional OTel.

### Trade-offs

Vendor UI acelera debug e cria dependência externa. OTel é excelente para tracing e não substitui schema científico. Eventos próprios garantem portabilidade.

### Impactos

- **Direto:** dois canais e correlation IDs.
- **Indireto:** observability pode ser plugada sem mudar bundles.
- **Exterior:** laboratório não precisa enviar dados a SaaS.
- **Subjetivo:** preserva soberania e confiança sobre dados.

### Reversibilidade

Média.

### Reavaliar quando

Operação de serviço exigir backend observability padrão; ainda assim eventos permanecem.

---
