# Ownership de decisões

## Human-owned

- licença e distribuição;
- produto e posicionamento;
- budget pago;
- publicação de provider outputs;
- claims externos finais;
- compatibility promises;
- uso de marca e hosted strategy.

## Maintainer-owned dentro de ADRs aceitas

- detalhes reversíveis de implementação;
- refactors sem change de contract;
- test fixtures e internal APIs;
- performance tuning dentro de invariants;
- bug fixes.

## Agent-owned somente como execução

Agentes podem escolher detalhes locais quando todos são verdadeiros:

- não existe gate pendente;
- ADR/requirement permite;
- mudança é reversível;
- não altera claim, protocol, license, privacy ou public API;
- decisão e rationale aparecem no PR.

Conflito sobe ao Orquestrador; impacto humano sobe ao Mestre Mael.
