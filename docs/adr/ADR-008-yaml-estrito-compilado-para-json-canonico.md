---
id: ADR-008
title: "YAML estrito compilado para JSON canônico"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-008: YAML estrito compilado para JSON canônico


**Status recomendado:** aceitar.  
**Decisão:** autoria YAML, validação Pydantic e hash de JSON canônico.

### Opções

1. YAML.
2. JSON.
3. TOML.
4. Hydra.
5. CUE/Jsonnet.
6. Python config.

### Trade-offs

JSON é preciso e hostil para manifests longos. TOML degrada em estruturas profundas. Hydra e DSLs trazem composição poderosa e semântica que precisa ser auditada. Python config é expressivo e não declarativo. YAML estrito tem armadilhas, mitigadas por parser seguro, schema e resolved output.

### Impactos

- **Direto:** manifests legíveis, schemas exportáveis.
- **Indireto:** reproducibility depende do resolved JSON, não da sintaxe YAML.
- **Exterior:** baixa barreira para papers e exemplos.
- **Subjetivo:** reduz a sensação de “configuração como programação”, preservando poder suficiente.

### Reversibilidade

Média, pois source format pode ganhar adapters. O resolved schema é o contrato real.

### Reavaliar quando

Experimentos exigirem composição que não caiba em matriz e patches explícitos.

---
