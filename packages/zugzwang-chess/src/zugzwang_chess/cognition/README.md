# cognition — percepção L0 do CognitiveBoard (CB-WO-03)

Fatos determinísticos sobre posições de xadrez (PRD §8): `PositionPacket`
(§8.2), ações como objetos vinculados ao estado (§8.3), relações L0-R mínimas
(§8.4) e `PositionDelta` com reconstrução (§8.6).

## Garantias

- **Sem assistência oculta (TEST-010)**: nenhum evaluator, nenhum ranqueamento,
  nenhuma poda — verificado por varredura de AST em `tests/unit/test_chess_cognition.py`.
- **Determinismo**: mesmo estado + mesmo policy hash → mesmo `content_hash()`
  (o pacote não carrega timestamp/telemetria — metadados de execução ficam no
  envelope externo, §8.2).
- **Campos desabilitados ficam ausentes** (`None`), nunca substituídos por
  resumo equivalente (§8.2).
- **Cravada absoluta** é fato formal (§8.4); cravada relativa e termos
  estratégicos ("peça pendurada", "garfo") não existem aqui.
- **Delta adjacente** carrega a ação responsável e reconstrói a projeção-alvo
  (TEST-016); **delta arbitrária** nunca atribui a diferença a uma ação
  (TEST-017). O snapshot integral permanece a autoridade de replay.

## Microbenchmark (documentado, não é gate de CI)

Máquina do operador (2026-09-06, CPython 3.14.7, posição inicial, page_size=32):
**0,39 ms/packet** (n=200, warm). O custo domina é a enumeração legal do kernel
via `python-chess`; paginação evita materializar listas grandes por exposição.

## Cobertura de testes (PRD §36, TEST-001–018)

Implementados aqui: TEST-005 (paginação == conjunto do kernel), 006
(ACTION_STATE_MISMATCH), 008 (ataque ≠ captura), 009 (cravada absoluta),
010 (sem assistência oculta), 011 (roque), 012 (en passant + linha do rei),
013 (promoções), 014 (término automático), 015 (claim ≠ término), 016
(reconstrução do delta), 017 (comparação arbitrária).

Fora deste módulo (com dependência de persistência/sessão): TEST-001–004
(snapshot integral, FEN×história, âncora, raiz imutável) e TEST-018 —
encaminhados ao CB-WO-04/05.
