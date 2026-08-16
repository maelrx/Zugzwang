---
id: ADR-021
title: "Tool protocol próprio; MCP na borda"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-021: Tool protocol próprio; MCP na borda


**Status recomendado:** aceitar.  
**Decisão:** tools tipadas com assistance/provenance; adapter MCP posterior.

### Opções

1. callables Python.
2. MCP como core.
3. internal tool contract + MCP adapter.

### Trade-offs

Callables simples não carregam governança. MCP entrega interoperabilidade, mas não conhece a taxonomia científica do projeto. Adapter preserva ambos.

### Impactos

- **Direto:** ToolDescriptor e broker.
- **Indireto:** segurança e assistance tracking ficam uniformes.
- **Exterior:** futuro acesso ao ecossistema MCP sem lock-in.
- **Subjetivo:** não confunde protocolo popular com modelo de domínio perfeito.

### Reversibilidade

Média.

### Reavaliar quando

Tools externas forem requisito central do MVP.

---
