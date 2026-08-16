---
id: ADR-006
title: "Granularidade de pacotes"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-006: Granularidade de pacotes


**Status recomendado:** aceitar.  
**Decisão:** `core`, `runtime`, `chess`, `cli` e plugins de integração; não um pacote por conceito.

### Opções

1. Single distribution com módulos internos.
2. Quatro pacotes centrais + plugins.
3. Dezena de micro-packages.

### Trade-offs

Single distribution reduz boilerplate, mas torna instalação do core dependente de todas as bordas. Micro-packages maximizam isolamento teórico e version choreography real. O corte intermediário separa motivos concretos: pure core, runtime I/O, domínio, interface e integrações opcionais.

### Impactos

- **Direto:** dependency graph verificável.
- **Indireto:** APIs públicas precisam ser escolhidas conscientemente.
- **Exterior:** plugin authors instalam apenas contratos necessários.
- **Subjetivo:** evita “package confetti”, uma forma elegante de perder uma tarde para publicar quatro linhas.

### Reversibilidade

Média. Mover módulos é possível antes de 1.0, mas import paths são contratos.

### Reavaliar quando

Um package tiver público, dependências ou release cadence claramente autônomos.

---
