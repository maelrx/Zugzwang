# START HERE

Este arquivo é a entrada operacional para o operador humano e para os agentes de engenharia.

## 1. O que existe neste pacote

Este corpus contém:

- base científica e mapa da literatura;
- tese de produto e PRD;
- arquitetura greenfield e system design;
- requisitos funcionais e não funcionais;
- schemas preliminares de protocolo;
- catálogo de experimentos v0.1;
- ADRs e gates de decisão humana;
- roadmap M0 a M6;
- backlog inicial de implementação;
- estratégia de testes, segurança e supply chain;
- `AGENTS.md` raiz e instruções aninhadas;
- skills reutilizáveis para agentes Codex;
- material-fonte arquivado e manifesto de proveniência.

O kernel Python está implementado em `packages/` e `plugins/`, com `uv.lock`, CLI, SQLite/CAS e testes offline. Este corpus também preserva propostas e documentos históricos; implementação não equivale a todos os exit gates concluídos.

Antes de começar trabalho novo, consulte o [estado operacional e fila de PRs](docs/engineering/REPOSITORY_STATUS.md). As estratégias experimentais em branches não devem ser confundidas com a main.

## 2. Ordem de leitura humana

1. [README.pt-BR.md](README.pt-BR.md)
2. [docs/product/VISION.md](docs/product/VISION.md)
3. [docs/research/SCIENTIFIC_FOUNDATIONS.md](docs/research/SCIENTIFIC_FOUNDATIONS.md)
4. [docs/architecture/SYSTEM_DESIGN.md](docs/architecture/SYSTEM_DESIGN.md)
5. [docs/decisions/HUMAN_DECISION_GATES.pt-BR.md](docs/decisions/HUMAN_DECISION_GATES.pt-BR.md)
6. [docs/roadmap/ROADMAP.md](docs/roadmap/ROADMAP.md)
7. [docs/roadmap/BOOTSTRAP_BACKLOG.md](docs/roadmap/BOOTSTRAP_BACKLOG.md)

A leitura completa continua pelo [índice documental](docs/INDEX.md).

## 3. Ordem de execução para Codex

1. Ler `AGENTS.md`.
2. Ler o `AGENTS.md` mais próximo do diretório que será alterado.
3. Carregar a skill específica da tarefa.
4. Conferir `docs/decisions/DECISIONS.yaml`.
5. Recusar-se a cristalizar qualquer gate com `status: pending`.
6. Implementar apenas o milestone ativo.
7. Rodar quality gates locais.
8. Atualizar requisitos, ADRs e traceability quando o contrato mudar.
9. Produzir um change report com evidência de testes e riscos residuais.

## 4. Gates e execução

Os gates do scaffold M0 foram aceitos em 2026-08-16:

- `GATE-001`: licença e rules substrate;
- `GATE-002`: matriz Python;
- `GATE-004`: nome do CLI.

`GATE-003` e `GATE-006` também estão aceitos para captura privada e engine fornecido pelo operador. Gates 005 e 007-012 permanecem pendentes, com os defaults de DECISIONS.yaml. Esta organização não autoriza novos runs pagos, redistribuição de outputs ou publicação de packages.

## 5. Validação do pacote

```bash
uv sync --all-packages --all-extras --locked
uv run python scripts/validate_foundation.py --strict
uv run pytest -m "not e2e"
```

O script confere:

- JSON schemas parseáveis;
- YAML parseável;
- frontmatter mínimo de skills;
- IDs de ADR únicos;
- links Markdown relativos básicos;
- decisões referenciadas;
- arquivos obrigatórios;
- ausência de um `LICENSE` acidental antes da decisão humana.

## 6. Regra de ouro

Nenhum agente pode “resolver” uma ambiguidade científica mudando silenciosamente o protocolo. Alterou representação, retries, tools, legal moves, knowledge packet, budget, engine ou seletor: alterou a condição experimental.

## 7. O que cada nível de evidência prova (e o que não prova)

Ao comunicar resultados, distinga sempre estes quatro níveis — nunca trate um pelo outro:

1. **Implementação**: o código existe e os contratos estão tipados/testados. Não prova comportamento correto em execução.
2. **Teste offline (fake)**: a suíte `pytest -m "not e2e"` cobre mecanismos com backend/engine fakes determinísticos. Prova os mecanismos do kernel; não prova nada sobre nenhum modelo real.
3. **Evidência real local**: runs com provider/engine reais (suite 0.1, bateria overnight) gravados em bundle/CAS. Prova o que aconteceu naquele run específico; com `n=1` é exploração, não comparação.
4. **Reprodução independente**: exportar um bundle, importá-lo em workspace sem acesso ao original, reconstruir as projeções do event stream e obter as mesmas jogadas e métricas equivalentes (prova offline: `tests/integration/test_m4_bundle.py`). É o piso para qualquer claim de reprodução; não substitui replicação estatística.

Reprodução independente de máquina limpa e validação científica da suite completa continuam pendências explícitas do roadmap (issues #13/#14/#15, GATE-011 para execução paga).

