# Relatório de pipeline real — Zugzwang / MuseSpark 1.3 Free

Data da execução: 2026-09-04  (America/Sao_Paulo)

## Resultado executivo

O pipeline real ficou operacional no checkout oficial de `main`: o
MuseSpark 1.3 Free foi chamado pelo roteador local do ZCode/OpenCode, as
respostas passaram pelo contrato canônico do Zugzwang e os lances foram
persistidos em SQLite + CAS.

O Stockfish agora pode ser um oponente live configurável, separado do modelo
e do avaliador pós-hoc. Foram executados buckets 1000 (aproximado), 1320,
1500, 2000 e 2500. Os jogos de 8 e 16 plies terminaram por limite de teste;
nenhum deles foi contado como vitória, derrota ou empate.

## Ambiente verificado

- Roteador: `/home/maelrx/.config/opencode/opencode_router.py` via
  `opencode-router.service`, ativo em `127.0.0.1:8788`.
- Catálogo: 43 modelos (`9` Free e `34` Go); o modelo usado foi
  `muse-spark-1.3-contributor-free`.
- Transporte usado nos manifests: `provider.openai_compatible`, perfil
  `openai-responses`, `reasoning_effort=minimal`, sem segredo no manifesto.
- Engine: `/home/maelrx/.local/bin/stockfish`, Stockfish 16,
  SHA-256 `00628bd9c9855c1b7ff93d7f8d51b413586cdc6336fe637f9a14a61531a05aca`.
- UCI nativo anunciado pelo binário: `1320..3190`.
- `zugzwang doctor`: OK; migrations `0002`; 21 plugins descobertos; sem
  órfãos no CAS.

## Runs reais

| Cenário | Run | Evidência | Resultado |
|---|---|---:|---|
| Move-selection direto | `run_eMMMty-iHLEKDs108nDrOg` | 1 chamada, `e2e4` | COMPLETED |
| MuseSpark de brancas vs random | `run_66KG7xsf8yD62orx1nTqcw` | 8 plies / 4 chamadas | COMPLETED |
| Random de brancas vs MuseSpark | `run_5b_BKC2EJXbSXxnRyJBDXw` | 8 plies / 4 chamadas | COMPLETED |
| MuseSpark vs MuseSpark | `run_3QG2BcscngkzWtZDK2ZiaQ` | 8 plies / 8 chamadas | COMPLETED |
| Stockfish bucket 1000 | `run_m9QF-wqQum8EL-PK9ZCXWg` | 8 plies / 4 chamadas | COMPLETED |
| Stockfish bucket 1000 estendido | `run_8YCLLyF__OfL3k9BJyD5Rw` | 16 plies / 8 chamadas | COMPLETED |
| Stockfish nativo 1320 | `run_0ICQztiklZ4hbNhjCVdwKA` | 8 plies / 4 chamadas | COMPLETED |
| Stockfish nativo 1500 | `run_SsQyv-AJHZxd05ZDjLbJrw` | 8 plies / 4 chamadas | COMPLETED |
| Stockfish nativo 2000 | `run_4kXZqNpnvE4J0YGT28JSgQ` | 8 plies / 4 chamadas | COMPLETED |
| Stockfish nativo 2500 | `run_LRDOi1EAe9FxbQMiSW9TNg` | 8 plies / 4 chamadas | COMPLETED |
| Stockfish 1500 de brancas vs MuseSpark | `run_uKVXfLq_wxXtuGDSqLiHwA` | 8 plies / 4 chamadas | COMPLETED |
| Grounded vs Stockfish 1500 estendido | `run_IIeEUkquzikTWy2vQdZ8hA` | 16 plies / 8 chamadas | COMPLETED |
| Grounded real | `run_IJouHzuDfUJJh_2Nx8bJ2g` | 1 chamada | COMPLETED |
| Reason-Then-Ground real | `run_d-KCcttUm1uG1TRiqQlWsg` | 2 chamadas | COMPLETED |
| Repair real | `run_ut8hyZ99mMKMZzdxQKHBMA` | 1 chamada | COMPLETED |
| Structured real | `run__1n0JBGE1wKvpkA3ZcHUbA` | 1 resposta JSON | COMPLETED |
| State reconstruction real | `run_Yg77arlbAvQVbwLzpBJ0mQ` | 2 episódios, ambos exact match 1.0 | COMPLETED |
| RGB multimodal real | `run_cCBcBPX4aMigfOxdH7oETA` | request com `text + image/png` | COMPLETED |

Na partida grounded de 16 plies, a avaliação Stockfish 1500 somente dos oito
lances do MuseSpark produziu 23 observações: concordância com o melhor lance
`0.375`, CPL médio `95.286`, máximo `530`, com 5 lances
`best_or_good`, 1 `mistake`, 1 `blunder` e 1 primeiro lance sem CPL. Isso é
uma medida do trecho executado, não um Elo do modelo.

## Semântica dos buckets de força

- `1320`, `1500`, `2000` e `2500` usam `UCI_LimitStrength=true` e o
  `UCI_Elo` nativo pedido; a configuração completa é gravada em cada step do
  Stockfish.
- `1000` não existe como `UCI_Elo` nativo nesse binário. O manifesto explicita
  `allow_approximate: true`; o engine recebe `UCI_Elo=1320` e `Skill Level=0`,
  enquanto a evidência registra `requested_elo=1000`,
  `effective_uci_elo=1320` e `strength_mode=approximate_skill_floor`.
- Sem essa autorização explícita, `elo: 1000` falha fechado e não consome
  chamada do provider (`run_3dQopKtdfJUrWUnwS-CT1Q`).

## Correções reveladas pelo teste real

1. O adapter OpenAI-compatible ganhou perfil Responses, normalização de
   resposta aninhada e forwarding apenas de extensões do próprio adapter.
2. O contexto assistant da segunda fase passou a usar `output_text`, exigido
   pelo proxy local.
3. O schema Structured passou a ser estrito (`additionalProperties: false`)
   e compatível com o provider.
4. Self-play explícito usa o mesmo backend/modelo/strategy nos dois lados e
   grava o segundo jogador como `model-opponent/...`.
5. Stockfish live grava política, hash, nome/autor UCI, força pedida/efetiva,
   opções e limite no step; não recebe prompt do modelo.
6. O avaliador pós-hoc ignora steps com `action_json.policy`, portanto mede
   somente os lances do modelo, e preserva `episode_id`.
7. O CLI separou `--output-dir` (bundle) de `--output` (formato); export/import
   foi verificado com 16 artefatos e checksum.

## Limites atuais

- Os runs desta rodada são smoke/continuidade de 8 ou 16 plies. Não há ainda
  evidência de vitória contra Stockfish; para isso é necessário um benchmark
  de 40–120 plies, múltiplas sementes, cores balanceadas e adjudicação por
  mate/afogamento/repetição.
- O modo `chess.direct` sem grounding falhou em uma partida longa no ply 10
  por `illegal_action`; o modo grounded completou 16 plies. Para uma escada
  de força, grounded é o protocolo mais adequado para separar capacidade de
  jogar de alucinação de UCI.
- `RunResult.output_dir` anuncia `.zugzwang/runs/<run_id>`, mas essa pasta não
  é materializada; a evidência continua disponível no SQLite/CAS e exportou
  corretamente, porém arquivos auxiliares por run ainda são uma lacuna.

## Verificação de qualidade

- `ruff check .`: OK.
- `ruff format --check .`: OK.
- `pytest -q`: `195 passed, 1 skipped, 6 deselected`.
- Todos os manifests locais deste relatório validaram pelo schema estrito.
