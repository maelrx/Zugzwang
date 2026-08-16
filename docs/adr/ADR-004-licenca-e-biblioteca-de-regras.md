---
id: ADR-004
title: "Licença e biblioteca de regras"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-001
date: "2026-08-12"
accepted_date: "2026-08-16"
source: "greenfield technical design 2026-08-11"
---

# ADR-004: Licença e biblioteca de regras

## Decisão ratificada (2026-08-16)

**Mestre Mael escolheu: GPL-3.0-or-later para todo o projeto + `python-chess` como rules substrate.**

Racional: menor engenharia inicial e máxima fidelidade funcional. `python-chess` entrega regras maduras, legal move generation, SAN/FEN/PGN e suporte UCI com grande base de testes. O custo é estratégico (copyleft forte para o conjunto), aceito pelo operador. A fronteira core/chess permanece: `zugzwang-core` não importa biblioteca de xadrez concreta e os tipos de `python-chess` não atravessam os contratos públicos de `zugzwang-chess`.


**Status recomendado:** decisão P0 a ratificar antes do primeiro release.  
**Decisão preferida:** Apache-2.0 para kernel e substrate de regras permissivo.

### Opções

1. GPL-3.0 para todo o projeto + `python-chess`.
2. Apache-2.0 + `cozy-chess`/binding próprio.
3. Apache-2.0 + sidecar permissivo JS.
4. Mixed-license monorepo com plugin GPL.

### Trade-offs

GPL + `python-chess` minimiza risco funcional e maximiza velocidade. Apache + permissivo maximiza embeddability, parceria e adoção empresarial, mas exige mais engenharia de SAN/PGN e packaging nativo. Mixed-license pode ser válido, porém é cognitivamente e juridicamente mais difícil de comunicar.

### Impactos

- **Direto:** muda dependências, packaging, testes e escopo de codecs.
- **Indireto:** determina quem pode incorporar o kernel e sob quais obrigações.
- **Exterior:** influencia contribuições de empresas, universidades e serviços fechados; também define quanto o ecossistema pode privatizar derivados.
- **Subjetivo:** licença funciona como sinal político e de governança. GPL enfatiza reciprocidade; Apache enfatiza disseminação e patent grant.

### Reversibilidade

Muito alta. Relicenciar exige consentimento de contribuidores; substituir rules core depois cria grande regressão potencial.

### Reavaliar quando

Antes do primeiro contributor externo ou publicação PyPI. Revisão jurídica recomendada para qualquer distribuição comercial.

---
