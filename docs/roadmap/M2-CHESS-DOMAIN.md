# M2: Domínio formal de xadrez

## Objetivo

Adicionar standard chess como environment plugin determinístico, mantendo biblioteca concreta atrás de adapter.

## Entry gates

- GATE-008 ratificado ou default standard-only aceito.
- Rules substrate selecionado por GATE-001.

## Entregáveis

- ChessState integral, including repetition-relevant history;
- UCI canonical action;
- FEN, ASCII, history e structured observation codecs;
- deterministic image renderer com metadata;
- legal action enumeration e opaque action indexing;
- move-selection, state-reconstruction e full-game tasks;
- random-legal opponent, replay policy e fake UCI engine;
- strict PGN mainline export;
- rare-rules fixtures: castling, en passant, promotion, fifty-move, repetition;
- metamorphic tests de rotate/color swap quando semanticamente válidos.

## Exit gate

Differential/property tests concordam com o substrate para corpus amplo; replay a partir do mesmo seed produz o mesmo estado, action hash e PGN.
