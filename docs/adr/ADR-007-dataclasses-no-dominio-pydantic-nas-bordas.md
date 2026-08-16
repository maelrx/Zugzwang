---
id: ADR-007
title: "Dataclasses no domínio, Pydantic nas bordas"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-007: Dataclasses no domínio, Pydantic nas bordas


**Status recomendado:** aceitar.  
**Decisão:** domínio imutável com dataclasses; manifests/events/DTOs Pydantic strict.

### Opções

1. Pydantic em tudo.
2. Dataclasses puras em tudo.
3. Separação domínio/boundary.
4. attrs/msgspec.

### Trade-offs

Pydantic everywhere acelera serialização, porém incentiva entidades anêmicas e coupling entre API, DB e domínio. Dataclasses everywhere exigem validação e schema manuais. Separar adiciona mappers pequenos, mas mantém invariantes e schemas conscientes.

### Impactos

- **Direto:** existe transformação explícita entre DTO e entidade.
- **Indireto:** futuras API e migrations não obrigam reescrever regras do domínio.
- **Exterior:** JSON Schema estável para tools e frontend.
- **Subjetivo:** um pouco mais de código, muito menos “objeto canivete suíço”.

### Reversibilidade

Média.

### Reavaliar quando

Mapping provar ser maior que a lógica ou uma biblioteca oferecer ganhos mensurados sem apagar boundaries.

---
