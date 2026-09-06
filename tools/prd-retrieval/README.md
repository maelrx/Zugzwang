# Contexto de retrieval determinístico — PRD CognitiveBoard (ZGW-0087)

Transforma o `Zugzwang_PRD_CognitiveBoard_v0.1.md` (7.351 linhas, 291 subseções,
~45k tokens) em um **contexto de retrieval determinístico e auditável** para sessões
longas de implementação por milestone: chunking por heading, BM25 + TF-IDF + RRF +
substring exata, facets de workflow (work orders, ADRs, gates, testes, PR/revisão).
**Stdlib-only** — rebuild reproduzível byte a byte, sem drift de dependências.

- Work order: [docs/work-orders/ZGW-0087.md](../../docs/work-orders/ZGW-0087.md)
- Fonte do desenho: benchmark executado sobre este exato documento
  (`~/.zcode/workspace/default/retrieval-bench-recovered/` — relatório consolidado
  `RELATORIO_retrieval_zugzwang_prd.md`; dados RX 5600 de 01/09 recuperados do rollout
  do Codex, `blob_08.txt`)

## Uso rápido

```bash
# construir (determinístico, <2 s) e verificar byte a byte
python3 tools/prd-retrieval/build_context.py
python3 tools/prd-retrieval/build_context.py --check

# consultar (rebuild automático e silencioso se o PRD mudar)
python3 tools/prd-retrieval/query_context.py "Quais tools o CognitiveBoard expõe?"
python3 tools/prd-retrieval/query_context.py "ADR-CB-007" --method exact --full
python3 tools/prd-retrieval/query_context.py "definition of done" --facet workflow --facet code-review
python3 tools/prd-retrieval/query_context.py "cobertura por gate" --section 36 --json --top-k 10
```

Saída padrão traz `chunk_id`, score, heading, **linha inicial–final do PRD** (citável)
e facets. `--json` entrega texto integral estruturado para consumo por agentes.

## Garantias de determinismo

1. **Rebuilds byte-idênticos**: nenhum timestamp nos artefatos derivados; chaves
   ordenadas, separadores fixos. Testado por `test_write_is_byte_identical_across_dirs`.
2. **Cobertura total**: toda linha do documento pertence a exatamente um chunk
   (front matter + cada subseção `##`, com split de blocos longos em limites de
   parágrafo, ≤ 1.800 chars). Testado contra o PRD real.
3. **Ordenação estável**: empates quebram por `(-score, chunk_id)`.
4. **Índice nunca stale silenciosamente**: `MANIFEST.json` grava o sha256 da fonte,
   `format_version` e os digests dos artefatos; a consulta reconstrói automaticamente
   quando o PRD muda ou quando qualquer artefato derivado não bate com o digest.
   Erros de CLI são estruturados (classe, onde, retryability, evidência) conforme
   `docs/engineering/CODING_STANDARDS.md`.

Artefatos derivados (`context/`) são **gitignored** — derivados, nunca evidência;
reconstruídos de forma idêntica em qualquer máquina a partir do documento + config.

## Números de aceitação (medidos com ESTE tool, no PRD real, 2026-09-06)

Ground truth: 50 perguntas naturais pt-BR herdadas do benchmark
([fixtures/retrieval/natural_questions.json](../../fixtures/retrieval/natural_questions.json))
+ cobertura total (cada subseção consultada pelo próprio título).

| Método | R@1 | R@10 | MRR | Latência/query |
|---|---|---|---|---|
| **rrf (default)** | **0.88** | 0.98 | **0.924** | ~0,3 ms |
| tfidf (1–2 gramas) | 0.84 | 0.98 | 0.889 | ~0,1 ms |
| bm25 (Okapi) | 0.82 | 0.98 | 0.885 | ~0,2 ms |
| exact (accent-folded) | — | — | — | citação literal |
| tfidf — cobertura 291 subseções | **1.0000** | 1.0000 | 1.0000 | — |

Barra de aceitação na CI offline (testes integram a suíte default; skip se o PRD não
estiver presente): rrf R@10 ≥ 0,94 e MRR ≥ 0,86; cobertura R@1 = 1,0. Os 6 erros de
top-1 restantes são o perfil paráfrase/indireção já caracterizado no benchmark — é o
caso onde embeddings densos somam (ver limitações).

## Facets (organização por workflow)

Derivados deterministicamente dos headings e da seção top-level
(`PRD_SECTION_FACETS` em `prd_retrieval.py`):

| Facet | Conteúdo | Exemplo de consulta |
|---|---|---|
| `work-order` | CB-WO-01..15 + §38 roadmap | `--facet work-order "CB-WO-05"` |
| `adr` | §41 catálogo ADR-CB-001..024 | `--facet adr "memória por snapshot"` |
| `gate` | quality gates, definition of ready/done | `--facet gate "pronto"` |
| `test` | §35–37 baterias, cobertura, aceitação | `--facet test "fixtures"` |
| `workflow` | PR, merge, branch, entrega, handoff | `--facet workflow "definition of done"` |
| `code-review` | revisão por perspectivas | `--facet code-review "perspectivas"` |
| `schema` | §42–43 contratos, tools, DDL | `--section 42 "board_expand"` |
| `invariant` / `requirement` / `hypothesis` | INV-n / RF-n / HY-n | `--json "INV-04"` |
| `roadmap`, `walkthrough`, `traceability`, `handoff`, `memory`, `budget`, `durability`, `errors`, `glossary`, `decision`, `state-machine`, `doc-review` | por seção | `--section 44` |

## Playbook de sessão longa (milestone → implementação linear)

```bash
# 0. Início de sessão: validar que o contexto casa com o PRD atual
python3 tools/prd-retrieval/build_context.py --check

# 1. Milestone/work order corrente: escopo e critérios de aceite
python3 tools/prd-retrieval/query_context.py "CB-WO-05 facade e executor" --facet work-order --full

# 2. Branches/PR: o que define pronto e como é o fluxo
python3 tools/prd-retrieval/query_context.py "definição de pronto de uma PR" --facet workflow --full
python3 tools/prd-retrieval/query_context.py "pacote mínimo de entrega work order" --full

# 3. Code review: perspectivas obrigatórias da revisão
python3 tools/prd-retrieval/query_context.py "revisão por perspectivas" --facet code-review --full

# 4. Testes: baterias, cobertura mínima por gate, fixtures formais
python3 tools/prd-retrieval/query_context.py "cobertura mínima por gate" --facet test
python3 tools/prd-retrieval/query_context.py "property testing e mutation testing" --facet test

# 5. Gates humanos: o que NÃO pode ser decidido pelo agente
python3 tools/prd-retrieval/query_context.py "questões que exigem ratificação" --full

# 6. Contratos antes de codar: schema de tools e comando canônico
python3 tools/prd-retrieval/query_context.py "schema do comando canônico" --section 42

# 7. Falhas e recuperação: walkthrough técnico do caso em depuração
python3 tools/prd-retrieval/query_context.py "falha depois do commit" --section 44
```

## Limitações (honestas)

- **Sem embeddings densos**: o RX 5600 mediu dense/hybrid-score acima do lexical para
  paráfrases (R@10 1,000 no corpus de código), mas os GGUFs foram apagados do disco;
  o custo de reintroduzir inferência local não cabe nesta ordem. Os 6 erros de top-1
  do rrf são desse perfil. Evolução: plug `RRF` com um ranking denso externo.
- Subseções com um único parágrafo > 1.800 chars não são divididos (mesma semântica
  do benchmark).
- Só headings de nível 2 delimitam chunks (nível 3 fica no corpo) — paridade com o
  benchmark validado.
- O texto de cada chunk repete o título na primeira linha (peso de título validado no
  benchmark); a linha `##` original permanece no corpo.
- `PRD_SECTION_FACETS` codifica o sumário do PRD v0.1; num novo major do documento,
  revisar o mapa (os facets por keyword continuam válidos).

## Atualização do documento (v0.1 → v0.2)

Nada a fazer no tool: a próxima consulta detecta o novo sha256 e reconstrói.
Para preservar rastreabilidade, anexe o novo sha256 ao relatório da sessão — o
manifesto derivado registra a fonte exata de cada build.
