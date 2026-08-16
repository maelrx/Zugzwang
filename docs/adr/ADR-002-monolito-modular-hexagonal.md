---
id: ADR-002
title: "Monólito modular hexagonal"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-002: Monólito modular hexagonal


**Status recomendado:** aceitar.  
**Decisão:** usar modular monolith + ports/adapters.

### Opções

1. Scripts/pipeline direto.
2. Monólito modular.
3. Microserviços/event bus.
4. Framework-centric architecture.

### Trade-offs

Scripts são ótimos para um paper isolado e ruins para compatibilidade, resume e plugins. Microserviços aumentam deploy, observabilidade distribuída, schemas de rede e failure modes sem necessidade de múltiplos times ou hosts. Framework-centric reduz código inicial, mas transfere a semântica do experimento para ciclos de vida externos.

### Impactos

- **Direto:** um processo, transações locais e debugging simples.
- **Indireto:** boundaries permitem extração posterior sem pagar custo distribuído agora.
- **Exterior:** instalação `uvx`/local mais atraente para adoção acadêmica.
- **Subjetivo:** transmite disciplina sem a cenografia de “enterprise architecture”. Contribuidores conseguem formar modelo mental do sistema.

### Reversibilidade

Média. Extração futura é possível se ports forem reais, não interfaces decorativas.

### Reavaliar quando

Execução precisar atravessar hosts, tenants ou workers independentes.

---
