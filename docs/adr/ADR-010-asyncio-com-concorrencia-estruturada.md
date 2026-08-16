---
id: ADR-010
title: "`asyncio` com concorrência estruturada"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-010: `asyncio` com concorrência estruturada


**Status recomendado:** aceitar.  
**Decisão:** async para network/subprocess I/O; domínio sync; TaskGroup/bounded queues.

### Opções

1. sync sequencial.
2. threads.
3. asyncio.
4. Trio/AnyIO.
5. distributed workers.

### Trade-offs

Sequencial desperdiça latência de providers. Threads são simples para SDKs sync, mas cancelamento e accounting ficam menos claros. Asyncio é stdlib e combina com HTTP/subprocesses. AnyIO melhora portabilidade de backend, porém outra abstração sem necessidade imediata.

### Impactos

- **Direto:** alta utilização de I/O e cancelamento coordenado.
- **Indireto:** providers sync precisam thread adapter explicitamente.
- **Exterior:** menor custo/tempo para grandes runs locais.
- **Subjetivo:** exige disciplina para não misturar blocking I/O no loop.

### Reversibilidade

Média/alta. Modelo async permeia ports, por isso deve ser escolhido cedo.

### Reavaliar quando

CPU local dominar ou distribuição for necessária.

---
