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

Não contém um runtime funcional. Os diretórios `packages/` e `plugins/` representam fronteiras e instruções, não uma implementação disfarçada.

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

## 4. Gates antes do scaffold

Os gates bloqueantes para o scaffold M0 são:

- `GATE-001`: licença e rules substrate;
- `GATE-002`: matriz Python;
- `GATE-004`: nome do CLI.

`GATE-003` bloqueia providers reais no M3, mas não o vertical slice fake-only de M0. Os demais possuem comportamento conservador documentado e precisam ser ratificados antes do milestone ou release que afetem.

## 5. Validação do pacote

```bash
python scripts/validate_foundation.py
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
