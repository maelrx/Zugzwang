---
id: ADR-024
title: "Engine UCI externa e pós-hoc"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-024: Engine UCI externa e pós-hoc


**Status recomendado:** aceitar.  
**Decisão:** process boundary; evaluator pós-hoc por padrão.

### Opções

1. library binding interno.
2. UCI process.
3. engine HTTP service.
4. engine live sempre.

### Trade-offs

UCI é padrão, auditável e desacoplado. Processos têm segurança/lifecycle. HTTP service serve distribuição e adiciona rede. Live engine melhora desempenho e altera assistência.

### Impactos

- **Direto:** subprocess manager e transcript.
- **Indireto:** separação clara entre decisão e avaliação.
- **Exterior:** qualquer UCI engine pode ser plugin.
- **Subjetivo:** impede que Stockfish seja contrabandeado para dentro do “LLM”.

### Reversibilidade

Alta conceitualmente; adapter permite outros backends.

### Reavaliar quando

Engine farms/distributed evaluation forem comprovadamente necessárias.

---
