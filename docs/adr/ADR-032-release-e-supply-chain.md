---
id: ADR-032
title: "Release e supply chain"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-032: Release e supply chain


**Status recomendado:** aceitar.  
**Decisão:** lockfile, SBOM, wheels, hashes e release automation gradual.

### Opções

1. source-only GitHub.
2. PyPI packages com CI.
3. containers como canal principal.
4. installer custom.

### Trade-offs

Source-only limita adoção. PyPI combina com Python/uv. Containers ajudam reproducibility de engines e serviço, mas são excessivos para library/CLI local. Rust extension exige wheel matrix.

### Impactos

- **Direto:** CI multiplataforma, trusted publishing e SBOM.
- **Indireto:** menos drift de ambiente.
- **Exterior:** instalação e auditoria melhores.
- **Subjetivo:** projeto parece utilizável, não apenas repositório de paper.

### Reversibilidade

Média.

### Reavaliar quando

GPU/local model stacks exigirem images especializadas.

---
