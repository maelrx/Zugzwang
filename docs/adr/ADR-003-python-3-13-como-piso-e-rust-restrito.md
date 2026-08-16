---
id: ADR-003
title: "Python 3.13 como piso e Rust restrito"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-002
date: "2026-08-12"
accepted_date: "2026-08-16"
source: "greenfield technical design 2026-08-11"
---

# ADR-003: Python 3.13 como piso e Rust restrito

## Decisão ratificada (2026-08-16)

**Mestre Mael escolheu: Python `>=3.13`, CI em 3.13 e 3.14, desenvolvimento principal em 3.13 no primeiro ciclo.**

Sem ilha Rust no v0.1: GATE-001 escolheu `python-chess`, eliminando a extensão PyO3 e sua wheel matrix. Se uma extensão nativa surgir depois, maturin/release multiplataforma volta à pauta via ADR substituta.


**Status recomendado:** aceitar com revisão de wheel matrix.  
**Decisão:** Python `>=3.13,<3.15` no início; Rust somente para rules core permissivo, se adotado.

### Opções

1. Python 3.12 para compatibilidade máxima.
2. Python 3.13 como equilíbrio.
3. Python 3.14-only.
4. Rust como linguagem principal.
5. TypeScript como linguagem principal.

### Trade-offs

Python domina APIs de modelos, dados e pesquisa. 3.14-only corre risco de wheels nativas atrasadas; 3.12 amplia compatibilidade, mas prolonga suporte de uma versão mais antiga. 3.13 permite typing/runtime moderno e já possui bom ecossistema. Rust principal elevaria correção/performance, porém aumentaria muito o custo de providers, ciência de dados e contribuição.

### Impactos

- **Direto:** CI testa 3.13 e 3.14 quando wheels existirem; 3.13 é baseline.
- **Indireto:** pequena extensão Rust exige maturin, release multiplataforma e toolchain em builds.
- **Exterior:** mantém baixo atrito para pesquisadores Python e não impede performance crítica.
- **Subjetivo:** evita tanto conservadorismo excessivo quanto fetiche de reescrita em Rust.

### Reversibilidade

Média. Baixar o piso é difícil se código usar features novas; elevar é simples.

### Reavaliar quando

Dependências científicas importantes não suportarem 3.13 ou quando 3.14 estiver universalmente coberto.

---
