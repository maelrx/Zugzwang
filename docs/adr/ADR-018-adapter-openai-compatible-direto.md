---
id: ADR-018
title: "Adapter OpenAI-compatible direto"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-018: Adapter OpenAI-compatible direto


**Status recomendado:** aceitar.  
**Decisão:** first-party, `httpx`, profiles explícitos.

### Opções

1. depender só do adapter multi-provider.
2. adapter direto.
3. exigir proxy LiteLLM.

### Trade-offs

O adapter direto duplica alguma integração, mas fornece baseline transparente e suporta servidores locais. “Compatible” não significa idêntico; profiles e capability probes são necessários.

### Impactos

- **Direto:** manutenção de endpoint comum.
- **Indireto:** permite comparar efeitos de normalização.
- **Exterior:** favorece OSS/local inference.
- **Subjetivo:** dá ao projeto um caminho independente e auditável.

### Reversibilidade

Baixa.

### Reavaliar quando

A diversidade de dialects superar o valor do adapter simples.

---
