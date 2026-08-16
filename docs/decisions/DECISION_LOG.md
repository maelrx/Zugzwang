# Log de decisões humanas

O log registra somente gates efetivamente ratificados. Decisões pendentes permanecem em `DECISIONS.yaml`.

| Data | Gate | Escolha | Autoridade | ADR | Consequência principal |
|---|---|---|---|---|---|
| 2026-08-12 | Fundação criada | Nenhum gate ratificado | Mestre Mael pendente | ADR-001..044 | Scaffold bloqueado apenas nas decisões irreversíveis |
| 2026-08-16 | GATE-001 | GPL-3.0-or-later + python-chess | Mestre Mael | ADR-004 | LICENSE GPL criada; rules substrate = python-chess atrás do port de `zugzwang-chess` |
| 2026-08-16 | GATE-002 | Python >=3.13, CI 3.13/3.14 | Mestre Mael | ADR-003 | pyproject/uv.lock com requires-python >=3.13; sem ilha Rust no v0.1 |
| 2026-08-16 | GATE-004 | `zugzwang` + `zgw` | Mestre Mael | ADR-037 | Dois entry points publicados em `zugzwang-cli` |
| 2026-08-16 | GATE-003 | Captura integral local privada; export público bloqueado | Mestre Mael | ADR-036 | Providers reais liberados para testes locais via adapter opencode |
| 2026-08-16 | GATE-006 | Binário oficial baixado localmente pelo operador (SF 18, sha256 f89b3b35...) | Mestre Mael | ADR-039 | Testes com engine real; sem redistribuição |

## 2026-08-16 — Suite inaugural 0.1 (ordem direta do operador)

- GATE-011 packet preparado (matriz texto deepseek-v4-flash / visão mimo-v2.5, piloto ~210 calls na assinatura). Status: pending, aguarda ratificação formal.
- K0-K7 oficial (ADR-047, emenda ADR-034) por decisão explícita do Mestre Mael.
- Renderer Pillow determinístico por decisão do Mestre Mael.
- Prompt hook no manifest incluído no batch (persona/few-shot) por decisão do Mestre Mael.
- Piloto e2e real executado (6 condições, posição Najdorf): verde; Stockfish 18 pós-hoc verde.

## 2026-08-16 — Modelo de visão padrão: mimo-v2.5 (diretiva do operador)

- Mestre Mael ordenou a troca do modelo de visão padrão para `opencode-go/mimo-v2.5`
  (assinatura OpenCode Go, attachment=true). Substituiu o candidato anterior (gpt-5.6-luna)
  em manifests, gerador, ADR-046, GATE-011 packet e docs da suite.
- GATE-011 continua pendente para ratificação formal de matriz/orçamento; a escolha do
  modelo de visão está registrada como diretiva do operador.
