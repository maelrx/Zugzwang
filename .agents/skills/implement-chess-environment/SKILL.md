---
name: implement-chess-environment
description: Implement or modify the standard-chess environment, state/action codecs, legal transitions, renderers, tasks, opponents, or PGN export behind the chess port.
---

# Implement chess environment

## Read

- accepted GATE-001/GATE-008 decisions;
- `docs/architecture/CHESS_DOMAIN.md`;
- `docs/protocol/CONTENT_PARTS_SPEC.md`;
- ADR-023, ADR-024, ADR-033 and ADR-042.

## Workflow

1. Keep concrete rules-library objects inside the adapter.
2. Represent full state, including history required for repetition.
3. Use UCI as canonical persisted action.
4. Keep SAN as an interface codec and label its information leakage.
5. Make legal action ordering and hash deterministic.
6. Implement transition as the only state mutation path.
7. Build FEN/ASCII/image renderers with renderer metadata.
8. Add rare-rules fixtures and property/differential tests.
9. Verify replay from seed/history.
10. Update assistance classification when exposing legal sets or semantic labels.

## Tests

- FEN/UCI roundtrip;
- legal parity against substrate;
- castling rights after rook/king moves;
- en passant lifecycle;
- underpromotion;
- repetition/fifty-move;
- illegal state/action rejection;
- deterministic image bytes;
- color/rotation metamorphic mappings where valid.

A correct legal-move list does not imply a good policy. Keep environment metrics separate from decision metrics.
