---
id: ADR-009
title: "Typer como CLI adapter"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-009: Typer como CLI adapter


**Status recomendado:** aceitar.  
**Decisão:** Typer para comandos; DTOs e services fora da CLI.

### Opções

1. argparse.
2. Click.
3. Typer.
4. custom CLI.

### Trade-offs

argparse reduz dependência e aumenta boilerplate. Click é estável e explícito. Typer adiciona type hints, help e subcommands com boa ergonomia, ao custo de uma camada sobre Click. O risco só aparece se decorators virarem application architecture.

### Impactos

- **Direto:** comandos rápidos de implementar e documentar.
- **Indireto:** futura API reutiliza services.
- **Exterior:** UX familiar e machine output estável.
- **Subjetivo:** contribuidor não precisa aprender um mini-framework interno para adicionar comando.

### Reversibilidade

Baixa se CLI for fina.

### Reavaliar quando

Typer limitar parsing ou estabilidade de interface.

---
