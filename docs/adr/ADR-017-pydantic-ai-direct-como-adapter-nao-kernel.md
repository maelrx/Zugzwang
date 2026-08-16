---
id: ADR-017
title: "Pydantic AI Direct como adapter, não kernel"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-017: Pydantic AI Direct como adapter, não kernel


**Status recomendado:** aceitar.  
**Decisão:** aproveitar cobertura de providers da API direta, sem Agent loop.

### Opções

1. SDKs nativos apenas.
2. Pydantic AI Agent.
3. Pydantic AI Direct.
4. LiteLLM core.

### Trade-offs

SDKs nativos maximizam fidelity e manutenção. Agent loop é produtivo e metodologicamente opaco para este caso. Direct requests oferece uma camada relativamente fina de tradução. Ainda existe risco de mudança e normalização.

### Impactos

- **Direto:** provider breadth cedo.
- **Indireto:** adapter precisa pinning e defensive mapping.
- **Exterior:** usuários acessam vários providers sem o projeto prometer equivalência perfeita.
- **Subjetivo:** usufrui do ecossistema sem ceder autoria arquitetural.

### Reversibilidade

Média, pois o contrato próprio isola.

### Reavaliar quando

Fidelity, estabilidade ou coverage forem inferiores ao custo de adapters nativos.

---
