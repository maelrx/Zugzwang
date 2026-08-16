# Posicionamento e ecossistema

## Categoria

Zugzwang ocupa a interseção de:

- LLM evaluation;
- agent harness engineering;
- experiment tracking;
- deterministic game environments;
- chess research;
- reproducible systems science.

Ele não compete frontalmente com uma arena, uma engine ou um provider router. Ele fornece o plano de controle metodológico que permite integrá-los sem confundir papéis.

## Comparáveis conceituais

| Família | Valor existente | Espaço do Zugzwang |
|---|---|---|
| LLM CHESS | partidas de modelos generalistas e ablações | protocolo mais geral, bundles, attribution e experiments as data |
| ChessArena | arena, tasks e treino | kernel menor, provider-agnostic e local-first |
| Game Arena | matches públicos | investigação causal e auditabilidade |
| OpenAI Evals / generic eval libs | execução de datasets e graders | ambiente sequencial formal, assistance classes e trajectories |
| Gymnasium / OpenSpiel | environments | model/provider calls, artifacts, retries e scientific provenance |
| MLflow / W&B | tracking | semantics específicas de agentic decisions e portable evidence |
| LangGraph / Temporal | workflows duráveis | runtime menor com semântica científica controlada |
| LiteLLM / provider SDKs | acesso a modelos | adapter substrate, nunca policy ou attribution authority |

## Wedge de adoção

A entrada não deve ser “instale uma plataforma”. Deve ser:

1. execute uma ablação de representação;
2. obtenha bundle e relatório auditável;
3. compare provider/modelo sem reescrever código;
4. publique o manifest junto ao resultado.

## Moat open source

O ativo cumulativo é um conjunto de contratos e artefatos adotados:

- manifest schema;
- event schema;
- bundle format;
- assistance taxonomy;
- experiment cards;
- provider contract tests;
- reusable suites;
- public reproduction corpus.

A vantagem não virá de esconder código. Virá da densidade metodológica e do custo de coordenação já absorvido.

## Expansão externa

Depois de maturidade no xadrez, outros ambientes só entram por RFC e devem provar:

- deterministic or reference state;
- verifiable action semantics;
- meaningful trajectory;
- evaluator provenance;
- value in decomposing capability.

Possíveis domínios futuros incluem gridworlds, formal tools, code repair sandboxes e games com estado verificável. Nenhum está no roadmap comprometido.
