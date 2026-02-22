<div align="right">

[🇺🇸 Read in English](README.md)

</div>

<div align="center">

# ♟ Zugzwang

**Motor de pesquisa reprodutível para empurrar LLMs aos seus limites no xadrez**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Pesquisa Ativa](https://img.shields.io/badge/status-pesquisa%20ativa-orange.svg)]()
[![Baseado em: LLM Chess](https://img.shields.io/badge/baseado%20em-LLM%20Chess%20arXiv%3A2512.01992-blueviolet)](https://arxiv.org/abs/2512.01992)

*"Zugzwang" — posição de xadrez onde todo lance disponível piora sua situação. Usamos isso como cadinho: LLMs conseguem raciocinar para sair dela?*

</div>

---

## O que é o Zugzwang?

Zugzwang é uma **plataforma de pesquisa modular e reprodutível** para estudar até onde LLMs generalistas conseguem chegar no xadrez usando apenas engenharia de prompts, RAG, few-shot learning, chain-of-thought, tool-use e orquestração multi-agente — **sem fine-tuning**.

O xadrez não é o objetivo em si, mas um **microscópio**. Sua natureza estruturada e verificável torna o domínio ideal para medir com rigor o gap entre capacidade bruta e performance aumentada de LLMs — lance por lance.

Este projeto estende o benchmark [LLM Chess](https://github.com/maxim-saplin/llm_chess) (Saplin et al., NeurIPS FoRLM 2025, [arXiv:2512.01992](https://arxiv.org/abs/2512.01992)) — o framework de referência para avaliar LLMs via jogo de xadrez — explorando sistematicamente as técnicas que aquele paper identificou como lacunas: prompting estruturado, calibração via few-shot, geração aumentada por recuperação (RAG) e orquestração mixture-of-agents.

---

## A Pergunta de Pesquisa

> *Usando exclusivamente técnicas de manipulação de LLMs — system prompts, RAG, few-shot, chain-of-thought, tool-use, orquestração multi-agente — e sem fazer fine-tuning em nenhum modelo, até onde é possível empurrar um LLM generalista no xadrez?*

---

## Motivação & Contexto

O paper LLM Chess (Saplin et al., 2025) estabeleceu que:

- A maioria dos LLMs **não consegue vencer um jogador aleatório** — eles falham em seguir instruções, não em jogar xadrez propriamente
- Apenas modelos com raciocínio explícito (o3, o4-mini, Grok 3 Mini) vencem consistentemente contra jogo aleatório
- O melhor modelo testado (o3 low) alcança apenas **Elo ~758** contra uma engine calibrada — pouco acima do jogador médio do chess.com
- O **formato FEN supera o tabuleiro Unicode** em até +21,7 pp para alguns modelos
- Fornecer o **histórico de lances reduz blunders** drasticamente (de 11,2% para 1,6% no o4-mini)
- **Mixture-of-Agents** combinando modelos de forte raciocínio + forte seguimento de instruções pode dobrar a taxa de vitórias e atingir 100% de partidas completadas

Porém, aquele benchmark usou um prompt simples e genérico, sem exemplos few-shot, sem RAG, sem chain-of-thought estruturado e sem loop de retry com feedback rico. O Zugzwang foi construído para preencher essas lacunas — com rigor e reprodutibilidade.

Fundações adicionais:

- **GPT-3.5-turbo-instruct** joga a ~1750 Elo consumindo PGN puro, sugerindo que LLMs possuem conhecimento latente de xadrez suprimido pelo instruction tuning ([Carlini, 2023](https://nicholas.carlini.com/writing/2023/chess-llm.html))
- **3 exemplos triviais de few-shot** melhoram dramaticamente a performance do GPT-4o no xadrez ([Dynomight, 2024](https://dynomight.net/chess/))
- **Transformers treinados em xadrez desenvolvem world models lineares** do estado do tabuleiro ([Karvonen, 2024](https://arxiv.org/abs/2403.15498))
- LLMs falham no xadrez principalmente por **acesso ao conhecimento**, não por capacidade de raciocínio ([arXiv:2507.00726](https://arxiv.org/abs/2507.00726))

---

## Arquitetura

O Zugzwang é construído em sete camadas progressivas, cada uma testável independentemente:

```
Camada 0 — Infraestrutura        Config, gerenciamento de secrets, validação de env
Camada 1 — Core Game Engine      BoardManager, game loop, jogadores LLM/Random/Engine
Camada 2 — Avaliação             Stockfish, qualidade de lances, estimativa de Elo (MLE)
Camada 3 — Estratégia            Biblioteca de prompts, montagem de contexto, few-shot, validação
Camada 4 — Conhecimento / RAG    Recuperação por fase: aberturas, táticas, finais
Camada 5 — Multi-Agente          Capability-MoA, agentes especializados, roteador híbrido
Camada 6 — Experiment Runner     Batch, resume, guardrails de budget, scheduling
Camada 7 — Análise               Estatísticas, gráficos, relatórios, dashboard React
```

**Invariantes de design fundamentais:**
- Nenhum lance ilegal é aplicado ao tabuleiro — jamais
- A avaliação do Stockfish **nunca** é exposta ao LLM durante a partida
- Todo artefato de partida é auto-contido e reprodutível a partir de seu seed
- A configuração é imutável após o início de um experimento

---

## Estrutura do Repositório

```
zugzwang-engine/
├── zugzwang/
│   ├── core/           # BoardManager, game loop, jogadores, protocolo
│   ├── providers/      # Anthropic, OpenAI, Google, z.ai, mock
│   ├── evaluation/     # Stockfish, qualidade de lances, Elo, métricas
│   ├── strategy/       # Prompts, montador de contexto, few-shot, validador
│   ├── knowledge/      # RAG: indexer, retriever, embeddings, vectordb
│   │   └── sources/    #   ECO aberturas, heurísticas Lichess, finais
│   ├── agents/         # Capability MoA, tático, posicional, final, crítico
│   ├── experiments/    # Runner, scheduler, tracker, resume
│   ├── analysis/       # Estatísticas, gráficos, relatórios
│   └── api/            # FastAPI layer (substitui o Streamlit)
├── zugzwang-ui/        # Frontend Vite + React + TypeScript
├── configs/
│   ├── defaults.yaml
│   ├── baselines/      # benchmark_compat.yaml, best_known_start.yaml
│   ├── ablations/      # Configs de condições experimentais
│   └── models/         # Overrides por modelo
├── data/               # ECO, puzzles, jogos anotados, vectordb (gitignored)
├── results/            # Artefatos de execução e relatórios (gitignored)
└── tests/
```

---

## Início Rápido

**Pré-requisitos:** Python 3.11+, uma chave de API de algum provider (ou use o provider `mock` para testes locais), e opcionalmente o [Stockfish](https://stockfishchess.org/download/) para avaliação.

```bash
# Instalar
pip install -e .[dev]

# Validar ambiente
zugzwang env-check --config configs/baselines/best_known_start.yaml

# Dry run (sem chamadas de API, sem partidas)
zugzwang run --config configs/baselines/best_known_start.yaml --dry-run

# Jogar uma partida
zugzwang play --config configs/baselines/best_known_start.yaml

# Rodar um experimento completo (30 partidas, salva artefatos em results/)
zugzwang run --config configs/baselines/best_known_start.yaml

# Avaliar qualidade dos lances com Stockfish
zugzwang evaluate --run-dir results/runs/<run-id>

# Iniciar o servidor de API
zugzwang api
```

### Configuração do Ambiente

Copie `.env.example` para `.env` e preencha suas chaves de API:

```bash
cp .env.example .env
# Edite .env e defina ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.
# Para Stockfish: defina STOCKFISH_PATH=/caminho/para/stockfish
```

---

## Referência de Comandos

| Comando | Descrição |
|---|---|
| `zugzwang run --config <path>` | Rodar um experimento completo |
| `zugzwang run --config <path> --dry-run` | Validar config sem executar |
| `zugzwang run --config <path> --resume` | Retomar execução mais recente compatível |
| `zugzwang run --config <path> --resume-run-id <id>` | Retomar execução específica |
| `zugzwang play --config <path>` | Jogar uma única partida |
| `zugzwang env-check --config <path>` | Validar credenciais de providers |
| `zugzwang evaluate --run-dir <path>` | Avaliação Stockfish pós-execução |
| `zugzwang api` | Iniciar servidor de API (porta 8000) |

### Overrides via CLI

Qualquer chave de configuração pode ser sobrescrita inline com `--set`:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set players.black.model=claude-opus-4-5 \
  --set strategy.board_format=fen \
  --set strategy.few_shot.enabled=true \
  --set strategy.few_shot.num_examples=3
```

---

## Funcionalidades Principais

### Dois Baselines

| Baseline | Config | Finalidade |
|---|---|---|
| `benchmark_compat` | `configs/baselines/benchmark_compat.yaml` | Reprodução fiel do protocolo LLM Chess |
| `best_known_start` | `configs/baselines/best_known_start.yaml` | Modo direto + FEN + lances legais + histórico (melhor config empiricamente conhecida) |

### Pipeline de Estratégia

O bloco `strategy` controla tudo que o LLM recebe:

```yaml
strategy:
  board_format: fen          # fen | ascii | combined | unicode (padrão: fen)
  provide_legal_moves: true
  provide_history: last_n
  history_length: 10
  few_shot:
    enabled: true
    num_examples: 3
    phase_specific: true     # Exemplos diferentes por abertura/middlegame/final
  validation:
    enabled: true
    max_retries: 3
    feedback_level: rich     # minimal | moderate | rich
```

### RAG — Recuperação Aumentada (Fase 4 — Disponível)

Recuperação de conhecimento determinística por fase, a partir de fontes locais:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.rag.enabled=true \
  --set strategy.rag.max_chunks=3 \
  --set strategy.rag.include_sources.eco=true \
  --set strategy.rag.include_sources.lichess=true \
  --set strategy.rag.include_sources.endgames=true
```

Fontes: princípios de aberturas ECO, heurísticas táticas/posicionais Lichess, teoria de finais.

Config de ablação RAG: `configs/ablations/rag_variants.yaml`

### Multi-Agente — MoA (Fase 5 — Disponível)

Orquestração Mixture-of-Agents com três modos configuráveis:
- `capability_moa`: proposers por perfil de capacidade (raciocínio/compliance/segurança)
- `specialist_moa`: proposers especializados (tático/posicional/final)
- `hybrid_phase_router`: roteamento de proposers por fase do jogo

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set strategy.multi_agent.enabled=true \
  --set strategy.multi_agent.mode=capability_moa \
  --set strategy.multi_agent.proposer_count=2
```

Configs de ablação disponíveis:
- `configs/ablations/moa_capability.yaml`
- `configs/ablations/moa_specialist.yaml`
- `configs/ablations/moa_hybrid_phase.yaml`

### Guardrails de Budget e Confiabilidade

```yaml
budget:
  max_total_usd: 5.00                         # Parada forçada
  estimated_avg_cost_per_game_usd: 0.55       # Para parada projetada

runtime:
  timeout_policy:
    enabled: true
    min_games_before_enforcement: 5
    max_provider_timeout_game_rate: 0.30      # Para se >30% das partidas darem timeout
    min_observed_completion_rate: 0.60
    action: stop_run
```

### Engine Player (UCI)

Jogue contra o Stockfish com nível de habilidade configurável:

```bash
zugzwang play --config configs/baselines/best_known_start.yaml \
  --set players.white.type=engine \
  --set players.white.depth=8
```

### Integração z.ai / GLM-5

```bash
zugzwang env-check --config configs/baselines/best_known_start_zai_glm5.yaml
zugzwang play --config configs/baselines/best_known_start_zai_glm5.yaml
```

### Frontend — FastAPI + React (Fase 7 — Em desenvolvimento)

A arquitetura atual usa um servidor **FastAPI** sobre os services Python existentes e um frontend **Vite + React + TypeScript** em `zugzwang-ui/`.

Iniciar o servidor de API:

```bash
pip install -e .[api]
zugzwang api                         # serve na localhost:8000
zugzwang api --reload                # modo dev com hot-reload
```

Em desenvolvimento, rodar o frontend separadamente:

```bash
cd zugzwang-ui && npm install && npm run dev   # Vite na localhost:5173
```

Em produção, `zugzwang api` serve o frontend compilado como arquivos estáticos — um processo, uma porta.

**Páginas do frontend:**

| Página | Rota | Descrição |
|---|---|---|
| Dashboard | `/` | Jobs ativos, runs recentes, gasto total |
| Run Lab | `/run-lab` | Configurar, validar e lançar experimentos |
| Job Monitor | `/jobs/:id` | Log em tempo real (SSE), barra de progresso, cancelar |
| Run Explorer | `/runs` | Navegar todos os runs, filtrar, ordenar |
| Run Detail | `/runs/:id` | Abas de métricas, qualidade de lances, config, evaluate |
| Game Replay | `/runs/:id/games/:n` | Replay do tabuleiro, métricas por lance, trace MoA |
| Comparação | `/runs/compare` | Comparação lado-a-lado com gráficos sobrepostos |
| Settings | `/settings` | Status de env check por provider |

**Stack:** FastAPI · Uvicorn · Vite · React 19 · TypeScript · TanStack Router · TanStack Query · Zustand · shadcn/ui · Tailwind · react-chessboard

Tipos TypeScript gerados automaticamente do schema OpenAPI do FastAPI — nunca escritos à mão:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts
```

Especificação completa de arquitetura: [`techdocs/FRONTEND_ARCHITECTURE.md`](../techdocs/FRONTEND_ARCHITECTURE.md)

---

## Artefatos de Execução

Cada execução cria um diretório em `results/runs/<run-id>/`:

```
results/runs/<run-id>/
├── resolved_config.yaml              # Config completa mesclada
├── config_hash.txt                   # Fingerprint determinístico da config
├── _run.json                         # Metadados de execução (secrets redactados)
├── games/
│   ├── game_0001.json                # Artefato por partida com trace completo
│   ├── game_0002.json
│   └── ...
├── experiment_report.json            # Métricas agregadas
└── experiment_report_evaluated.json  # Qualidade de lances + Elo (após evaluate)
```

Cada `GameRecord` inclui: sequência de lances, metadados de retry, uso de tokens, latência por lance, custo, motivo de encerramento e traces de RAG/MoA quando habilitados.

---

## Protocolo Experimental

O design experimental é estruturado para maximizar o sinal científico por real gasto — evitando refazer ablações que o paper base já cobriu.

| Fase | Objetivo | Condições |
|---|---|---|
| **1 — Calibração de Baseline** | Confirmar que nosso sistema replica os resultados do LLM Chess (±5%) | ~50 partidas |
| **2 — Ablação de Prompting** | Isolar impacto de: few-shot, CoT posicional, feedback rico no retry, formato de entrada | 30 partidas por condição |
| **3 — RAG Progressivo** | Medir ganho marginal de cada fonte de conhecimento (aberturas, táticas, finais) | 30 partidas por condição |
| **4 — Full Pipeline** | Melhor config contra Stockfish em múltiplos níveis — estimar Elo com IC de 95% | 50+ partidas por nível |
| **5 — Análise Cross-Model** | Rodar a config vencedora em todos os modelos testados | 30 partidas por modelo |

### Métricas

**Primárias:** Win Rate, Elo estimado (MLE), Game Completion Rate

**Qualidade dos Lances:** ACPL (Average Centipawn Loss), taxa de blunders, acordo com top-1 do Stockfish, distribuição de categorias (brilliant/excellent/good/inaccuracy/mistake/blunder)

**Por Fase do Jogo:** ACPL separado para abertura, middlegame e endgame; degradação temporal (ACPL como função do número do lance)

**Custo e Robustez:** Tokens por lance, custo por partida, taxa de lances ilegais, taxa de conclusão de protocolo

---

## Roadmap de Desenvolvimento

| Fase | Status | O que habilita |
|---|---|---|
| Fase 0 — Bootstrap | ✅ Completo | Config reprodutível, CLI, validação de env |
| Fase 1 — Core Engine | ✅ Completo | Partidas legais, todos os tipos de jogador, modos de protocolo |
| Fase 2 — Avaliação | ✅ Funcional | Scoring Stockfish, ACPL, Elo MLE, taxa de blunders |
| Fase 3 — Estratégia | ✅ Funcional | Prompts, montagem de contexto, few-shot, validação |
| Fase 4 — RAG | ✅ MVP | Recuperação local por fase, configs de ablação |
| Fase 5 — Multi-Agente | 🔄 Baseline+ | Modos capability, specialist e hybrid phase-router MoA |
| Fase 6 — Experiment Runner | 🔄 Parcial | Batch + resume + budget; queue scheduler pendente |
| Fase 7 — Análise | 🔄 Parcial | FastAPI + React dashboard em desenvolvimento |

**Próximos alvos:** MoA especialista/híbrido, scheduler com fila, visualizações comparativas e export de análise.

---

## Desenvolvimento

```bash
# Instalar com dependências de dev
pip install -e .[dev]

# Rodar todos os testes
pytest -q

# Instalar com dependências de API
pip install -e .[api]
zugzwang api --host 127.0.0.1 --port 8000
```

Os testes cobrem: legalidade do tabuleiro, hash de configuração, parsing de lances, políticas de retry, matemática do Elo, recuperação RAG, orquestração MoA, resume/dedup do runner, enforcement de budget.

---

## Referências

### Referências Primárias

1. **Kolasani, S., Saplin, M. et al.** (2025). *LLM CHESS: Benchmarking Reasoning and Instruction-Following in LLMs through Chess.* NeurIPS FoRLM 2025. [arXiv:2512.01992](https://arxiv.org/abs/2512.01992) · [Código](https://github.com/maxim-saplin/llm_chess)

2. **Karvonen, A.** (2024). *Emergent World Models and Latent Variable Estimation in Chess-Playing Language Models.* COLM 2024. [arXiv:2403.15498](https://arxiv.org/abs/2403.15498)

3. **Feng, X. et al.** (2023). *ChessGPT: Bridging Policy Learning and Language Modeling.* NeurIPS 2023. [arXiv:2306.09200](https://arxiv.org/abs/2306.09200)

4. **Zhang, Y. et al.** (2025). *Complete Chess Games Enable LLM Become A Chess Master.* NAACL 2025. [arXiv:2501.17186](https://arxiv.org/abs/2501.17186)

5. **Monroe, D. & Leela Chess Zero Team** (2024). *Mastering Chess with a Transformer Model.* [arXiv:2409.12272](https://arxiv.org/abs/2409.12272)

6. **Ruoss, A. et al.** (2024). *Amortized Planning with Large-Scale Transformers: A Case Study on Chess.* NeurIPS 2024. [arXiv:2402.04494](https://arxiv.org/abs/2402.04494)

7. **Anonymous** (2025). *Can Large Language Models Develop Strategic Reasoning? Post-training Insights from Learning Chess.* [arXiv:2507.00726](https://arxiv.org/abs/2507.00726)

### Blog Posts e Análises

8. **Carlini, N.** (2023). *Playing chess with large language models.* [nicholas.carlini.com](https://nicholas.carlini.com/writing/2023/chess-llm.html)

9. **Dynomight** (2024). *Something weird is happening with LLMs and chess.* [dynomight.net](https://dynomight.net/chess/)

10. **Dynomight** (2024). *OK, I can partly explain the LLM chess weirdness now.* [dynomight.net](https://dynomight.net/chess2/)

11. **Karvonen, A.** (2024). *Chess-GPT's Internal World Model.* [adamkarvonen.github.io](https://adamkarvonen.github.io/machine_learning/2024/01/03/chess-world-models.html)

---

## Licença

MIT. Veja [LICENSE](LICENSE).

---

<div align="center">
<sub>Construído com rigor, curiosidade e profundo respeito pelo jogo.</sub>
</div>
