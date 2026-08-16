---
id: ADR-005
title: "Monorepo com `uv` workspace"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-005: Monorepo com `uv` workspace


**Status recomendado:** aceitar.  
**Decisão:** múltiplos packages gerenciados juntos, um lockfile.

### Opções

1. Um pacote único.
2. `uv` workspace.
3. Poetry/PDM workspace.
4. Polyrepo.

### Trade-offs

Um pacote único é mais simples, mas providers e chess carregariam dependências opcionais e ciclos de release diferentes. Polyrepo melhora autonomia quando existem times independentes; hoje fragmentaria issues, CI e mudanças atômicas. `uv` workspace mantém lock consistente e permite pacote principal + plugins.

### Impactos

- **Direto:** cada membro tem `pyproject.toml`; CI pode testar packages separadamente.
- **Indireto:** single lockfile impede versões conflitantes entre plugins first-party, algo desejável no núcleo, mas limita experimentos com dependências incompatíveis.
- **Exterior:** contribuição e bootstrap ficam mais simples que polyrepo.
- **Subjetivo:** estrutura parece profissional sem sacrificar velocidade.

### Reversibilidade

Baixa/média. Migrar workspace tooling é mecânico; dividir histórico em repos é mais trabalhoso.

### Reavaliar quando

Plugins third-party precisarem ambientes incompatíveis ou release governance independente.

---
