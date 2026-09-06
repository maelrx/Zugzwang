# Roadmap do Zugzwang Research Kernel

O roadmap é ordenado por redução de risco, não por aparência de produto. O kernel só sobe de camada depois de provar a camada anterior com fakes, contratos e replay. Web UI, serviço remoto e treinamento não pertencem ao caminho crítico do v0.1.

## Estado de integração em 2026-09-05

Existe runtime funcional e suíte offline. Extensões R5/R7, evidências e viewer estão em PRs e branches de pesquisa; isso não ratifica gates nem conclui M5/M6. A manutenção atual consolida a main e mantém questões científicas e de compatibilidade abertas. Consulte o [mapa operacional](../engineering/REPOSITORY_STATUS.md).

O viewer experimental permanece em revisão separada. Sua incorporação ao produto exige registrar escopo e critérios; esta atualização não altera o anti-roadmap.

## Sequência executiva

```mermaid
flowchart LR
    M0[M0 Constituição] --> M1[M1 Runtime local]
    M1 --> M2[M2 Xadrez formal]
    M2 --> M3[M3 Providers R0-R2]
    M3 --> M4[M4 R3 + evaluation + bundles]
    M4 --> M5[M5 Robustez]
    M5 --> M6[M6 Suite científica]
    M6 -. depois .-> API[API adapter]
    API -. depois .-> WEB[Web UI]
```

| Milestone | Nome | Escopo | Entry gate | Exit gate |
|---|---|---|---|---|
| `M0` | Constituição do kernel | Contratos, workspace, boundaries e CI offline | GATE-001, GATE-002, GATE-004 | Schemas gerados; fake-only vertical slice; architecture tests verdes |
| `M1` | Execução local mínima | Manifest resolver, SQLite/CAS, event stream, budgets, interruption/resume | M0 | Run fake reproduzível, interrompível, retomável e exportável |
| `M2` | Xadrez formal | Environment standard chess, UCI, renderers e tarefas locais | GATE-008 + M1 | State/action/tracking/property tests e replay determinístico |
| `M3` | Providers e R0-R2 | ModelBackend, fake, Pydantic AI Direct, OpenAI-compatible, retries explícitos | GATE-003 + M2 | Dois adapters contract-tested sem rede no CI |
| `M4` | R3, avaliação e bundles | Structured strategy, Stockfish post-hoc, métricas, Parquet/DuckDB | GATE-006, GATE-009 + M3 | Bundle autocontido validado e reavaliável offline |
| `M5` | Robustez de plataforma | Plugins, fault injection, supply chain, security, compatibility | GATE-007, GATE-012 + M4 | Release candidate com SBOM, migrations e plugin compatibility tests |
| `M6` | Primeira suite científica | REP, GROUND, SKILL, MM, DEMO e promoção controlada a full-game | GATE-005, GATE-011 + M5 | Relatório preregistrado, bundles publicáveis e claims auditados |

## Políticas de progressão

- Um milestone pode ter implementação parcial, mas não é declarado concluído sem seu exit gate.
- Um recurso novo precisa localizar-se em um requisito e em um milestone.
- Trabalho paralelo só é permitido quando não cria dependência circular nem antecipa decisão humana.
- Um experimento pago não começa antes de dry-run, fake replay e budget projection.
- Nenhum ganho científico é anunciado a partir de smoke test.
- O roadmap pode mudar por ADR; não muda por conveniência silenciosa durante implementação.

## Fora do v0.1

- Web UI e API pública;
- daemon multiusuário;
- Postgres e object storage remoto;
- workers distribuídos;
- RAG/vector database;
- treinamento SFT/RLVR;
- marketplace de plugins;
- variant families além do contrato mínimo;
- leaderboard público único;

## ZGW-0079 foundation slice

The current work order adds the first research-kernel pieces without changing
the modular-local deployment plan: direct per-step evidence, provider wire
telemetry, explicit legality exposure, EvaluationRun generations and a local
R6 model-only search graph. Full interactive search and any public export still
need their own gates.
- execução arbitrária de código por agentes.

## Documentos por milestone

- [M0](M0-CONSTITUTION.md)
- [M1](M1-LOCAL-RUNTIME.md)
- [M2](M2-CHESS-DOMAIN.md)
- [M3](M3-PROVIDERS-AND-STRATEGIES.md)
- [M4](M4-EVALUATION-AND-BUNDLES.md)
- [M5](M5-HARDENING.md)
- [M6](M6-SCIENTIFIC-SUITE.md)
