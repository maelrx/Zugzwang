# Modelo operacional dos agentes Codex

## 1. Autoridade

O Zugzwang separa execução delegada de decisão soberana.

| Papel | Autoridade | Não pode fazer |
|---|---|---|
| **Mestre Mael** | ratificar gates, aceitar ADRs irreversíveis, mudar produto e claims | delegar responsabilidade final sem registro |
| Orquestrador | decompor trabalho, selecionar skills, ordenar agentes, integrar handoffs | inventar decisão humana, ocultar conflito |
| Arquiteto | propor contracts, ADRs e trade-offs | aceitar gate humano ou implementar fora do escopo |
| Implementador | produzir mudança bounded por issue/ADR | ampliar escopo, criar fallback/retry oculto |
| Research auditor | verificar literatura, protocolo, claims e contamination | transformar inferência em resultado observado |
| Reviewer | procurar defeitos, boundary violations e risco | aprovar o próprio trabalho sem reviewer independente |
| Release custodian | validar supply chain, migrations e release evidence | publicar com gates bloqueadores pendentes |

## 2. Unidade de trabalho

Todo trabalho de agente começa com um **Work Order**:

```yaml
work_order:
  id: ZGW-XXXX
  objective: "one bounded outcome"
  milestone: M0
  requirements: [FR-XXX, NFR-XXX]
  adrs: [ADR-XXX]
  gates_required: [GATE-XXX]
  skill: bootstrap-workspace
  allowed_paths: []
  forbidden_paths: []
  evidence_required: []
  stop_conditions: []
```

Sem work order, o agente pode analisar e preparar proposta, mas não modificar arquitetura ou código.

## 3. Ciclo obrigatório

1. **Orientar:** ler `AGENTS.md`, gate state, milestone, ADRs e requirements.
2. **Checar bloqueios:** nenhum gate pendente pode ser inferido.
3. **Selecionar skill:** usar a skill mais específica; não improvisar workflow quando já existe uma.
4. **Inspecionar estado real:** código, tests, migrations e docs, sem confiar em resumo antigo.
5. **Propor delta mínimo:** declarar arquivos e invariantes afetados.
6. **Implementar por slices:** manter cada commit conceitualmente reversível.
7. **Testar localmente:** unit, contract, architecture e fault tests cabíveis.
8. **Atualizar rastreabilidade:** requirements, ADR, schema, changelog e docs quando necessário.
9. **Produzir handoff:** fatos, mudanças, evidência, riscos, decisões pendentes.

## 4. Handoff packet

```yaml
handoff:
  work_order: ZGW-XXXX
  status: complete | partial | blocked
  changed_paths: []
  tests:
    passed: []
    skipped: []
    failed: []
  invariants_checked: []
  requirements_satisfied: []
  decisions_needed: []
  risks_introduced_or_changed: []
  follow_up: []
```

“Tests pass” sem comando e resultado é uma afirmação insuficiente.

## 5. Regras científicas para agentes

- Não combinar regimes `R`, `H` ou `K` diferentes no mesmo resultado agregado sem slice explícito.
- Não tratar retry, tool, legal actions, search ou engine como plumbing neutro.
- Não usar LLM-as-judge como única verificação de fatos enxadrísticos.
- Não editar outcomes depois de ver os resultados de uma condição congelada.
- Não substituir resultado nulo por nova hipótese pós-hoc sem rotulá-la como exploratória.
- Não publicar raw provider output sem GATE-003/GATE-005.
- Não chamar smoke test de benchmark.

## 6. Política de contexto

O root `AGENTS.md` define invariantes globais. Arquivos `AGENTS.md` aninhados especializam o contexto no package/plugin. A instrução mais próxima do arquivo modificado prevalece, desde que não contradiga um gate humano ou requisito global.

A documentação oficial do Codex descreve essa descoberta hierárquica de `AGENTS.md` e recomenda arquivos aninhados para instruções específicas de subárvore. Skills ficam em `.agents/skills/<name>/SKILL.md`, com descrição acionável e carregamento progressivo.

## 7. Stop conditions

Um agente deve parar e devolver um decision packet quando:

- gate humano bloqueador está pendente;
- fonte jurídica/provider não é suficientemente clara;
- change exige quebrar contract público fora da compatibility policy;
- requisito conflita com ADR aceita;
- teste revela possível corrupção de evidência;
- scope excede paths permitidos;
- custo real excederia budget aprovado;
- a única forma de avançar seria esconder assistência ou falha.

Parar por um bloqueio real é sucesso operacional, não fracasso do agente.
