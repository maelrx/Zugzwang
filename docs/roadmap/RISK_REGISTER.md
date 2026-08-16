# Registro de riscos

| ID | Risco | Probabilidade | Impacto | Mitigação/controle |
|---|---|---|---|---|
| `R-001` | Licença incompatível entre kernel e rules library | Alta | Crítico | Ratificar GATE-001 antes do scaffold; revisão jurídica para distribuição. |
| `R-002` | Provider drift altera resultados silenciosamente | Alta | Alto | Snapshot exato, data, raw response, capabilities e re-runs temporais. |
| `R-003` | Harness assistance é atribuída ao modelo | Alta | Crítico | H/K taint tracking, protocol violation e leaderboards separados. |
| `R-004` | Retries/fallbacks ocultos inflam força | Alta | Crítico | Cada attempt e policy explícitos; nenhum retry no SDK fora do adapter. |
| `R-005` | SQLite writer vira gargalo | Média | Médio | Single writer, batch pequeno, métricas; Postgres só por evidência. |
| `R-006` | Crash após request cria outcome desconhecido | Alta | Alto | Attempt `outcome_unknown`, idempotency quando disponível, nunca repetir cegamente. |
| `R-007` | Artifacts explodem disco e expõem dados | Alta | Alto | CAS dedup, quota, retention policy, private/public derivative. |
| `R-008` | Schema público congela erro cedo | Média | Alto | Version spaces independentes, upcasters, experimental plugin API. |
| `R-009` | Pydantic AI muda message parts | Média | Médio | Pin, defensive adapter, raw preservation, contract tests. |
| `R-010` | OpenAI-compatible não é realmente compatível | Alta | Médio | Dialect capabilities, golden fixtures e adapter-specific metadata. |
| `R-011` | Stockfish config torna métricas incomparáveis | Alta | Alto | Hash/version/options/budget/PV policy no metric provenance. |
| `R-012` | Contaminação de puzzles/positions | Alta | Alto | Temporal, synthetic, random-legal, hidden sets e corpus hashes. |
| `R-013` | Few-shot/skills vazam próximo lance | Média | Crítico | Transposition exclusion, provenance e controls token-pareados. |
| `R-014` | Imagem é regenerada de forma não reprodutível | Média | Médio | Renderer version, exact bytes, orientation/theme/hash no CAS. |
| `R-015` | Agentes Codex fazem decisão humana | Média | Crítico | DECISIONS.yaml, stop conditions e gate validator. |
| `R-016` | Micro-packages causam release choreography | Média | Médio | Poucos packages físicos; publicação agregadora inicialmente. |
| `R-017` | Frontend invade o core cedo | Média | Médio | Application services e DTOs, sem API/Web até pós-M6. |
| `R-018` | Testes reais de provider tornam CI instável/caro | Alta | Médio | CI offline; e2e real opt-in e budget-gated. |
| `R-019` | Métrica única vira ranking enganoso | Alta | Alto | Capability vector, slices e claims policy. |
| `R-020` | Pesquisa vira produto sem modelo sustentável | Média | Médio | OSS kernel independente; hosted plane futuro sem mutilar protocolo. |
| `R-021` | Plugin malicioso acessa host e secrets | Média | Crítico | First-party only inicialmente; trust metadata; future subprocess isolation. |
| `R-022` | WAL em SQLite vulnerável a versões problemáticas | Baixa | Alto | Runtime doctor e mínimo seguro conforme ADR-044. |
| `R-023` | Reasoning textual é tratado como mecanismo causal | Alta | Alto | Factual/faithfulness metrics e linguagem epistemicamente controlada. |
| `R-024` | Custo USD fica incorreto por cache/discount | Alta | Médio | Usage factual separado de estimated cost; snapshot registry. |

## Escalada

Riscos críticos bloqueiam merge quando o change aumenta sua exposição sem controle verificável. O reviewer deve apontar o ID do risco no PR. Novos riscos recebem ID estável e owner antes de serem aceitos.
