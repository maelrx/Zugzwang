---
id: ADR-014
title: "CAS + eventos + projections"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-014: CAS + eventos + projections


**Status recomendado:** aceitar.  
**Decisão:** híbrido, não DB-only nem event sourcing puro.

### Opções

1. tudo no DB.
2. tudo em diretórios.
3. event sourcing integral.
4. hybrid artifacts/events/projections.

### Trade-offs

DB-only cresce com blobs e dificulta compartilhamento. Files-only perde transactional indexing. Event sourcing puro eleva complexidade de projection/versioning. Hybrid preserva evidência portável e operação simples.

### Impactos

- **Direto:** commit protocol e GC são necessários.
- **Indireto:** run bundle independe do workspace.
- **Exterior:** resultados podem ser publicados e reavaliados sem copiar um banco inteiro.
- **Subjetivo:** artefato científico torna-se produto de primeira classe, não sobra de logs.

### Reversibilidade

Alta, pois IDs e bundle format viram contratos centrais.

### Reavaliar quando

Objetos crescerem a ponto de exigir S3 local/remoto ou streaming de blobs.

---
