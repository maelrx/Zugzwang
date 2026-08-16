# Console de decisões do Mestre Mael

Este documento é o ponto de controle humano do Zugzwang. Ele reúne escolhas com impacto jurídico, distributivo, científico, de compatibilidade ou de identidade pública. Agentes Codex podem pesquisar opções, produzir evidência e preparar uma recomendação, mas **não podem ratificar uma decisão em nome do operador**.

O estado executável vive em [`DECISIONS.yaml`](DECISIONS.yaml). Esta página explica os trade-offs. A decisão só existe quando os dois artefatos e a ADR correspondente concordam.

## Protocolo de ratificação

1. Selecionar uma opção ou registrar uma alternativa nova.
2. Escrever racional, impactos aceitos e hipótese de reversão.
3. Assinar `approved_by: Mestre Mael` e data ISO.
4. Alterar a ADR de `proposed` para `accepted`, ou criar uma ADR substituta.
5. Atualizar requisitos, roadmap e scaffold afetados.
6. Executar `python scripts/validate_foundation.py --strict-decisions`.

Uma recomendação arquitetural é uma posição argumentada, não consentimento implícito.

## Visão geral

| Gate | Decisão | Bloqueio | Estado | Recomendação atual |
|---|---|---|---|---|
| [GATE-001](#gate-001) | Licença do kernel e substrato de regras | `M0 scaffold público` | **Pendente** | Apache-2.0 no kernel + substrato permissivo de regras atrás de port próprio |
| [GATE-002](#gate-002) | Piso de Python e matriz de suporte | `Criação de pyproject e lockfile` | **Pendente** | Python >=3.13; CI em 3.13 e 3.14; desenvolvimento principal em 3.13 no primeiro ciclo |
| [GATE-003](#gate-003) | Retenção padrão de prompts, responses e reasoning | `Defaults de artifact policy` | **Pendente** | Captura integral local privada; export público exige política explícita de derivação/redação |
| [GATE-004](#gate-004) | Nome do CLI público | `Publicação do entry point` | **Pendente** | Comando canônico `zugzwang`; alias curto `zgw` quando não houver colisão |
| [GATE-005](#gate-005) | Redistribuição de outputs e artefatos de providers | `Export público de bundles reais` | **Pendente** | Registry de políticas por provider/modelo + confirmação explícita antes de export público |
| [GATE-006](#gate-006) | Aquisição e distribuição do Stockfish | `UX do evaluator Stockfish` | **Pendente** | Binário fornecido pelo usuário no v0.1; downloader separado e juridicamente auditado depois |
| [GATE-007](#gate-007) | Estabilidade inicial da API de plugins | `Expectativa pública de compatibilidade` | **Pendente** | Experimental até 0.3; compatibility window de uma minor; contracts explicitamente versionados |
| [GATE-008](#gate-008) | Escopo de variantes enxadrísticas no primeiro release | `Contrato do environment` | **Pendente** | Standard chess como happy path; variant_id no contrato; Chess960 apenas como capability futura |
| [GATE-009](#gate-009) | Governança do registry de custos | `Claims econômicos` | **Pendente** | Snapshots manuais versionados por experimento; provider usage é fonte de verdade quando disponível |
| [GATE-010](#gate-010) | Idioma canônico da documentação | `Política de contribuição internacional` | **Pendente** | README e contrato público em inglês; engenharia canônica inicialmente em PT-BR; tradução progressiva com source-of-truth explícito |
| [GATE-011](#gate-011) | Matriz inaugural de modelos e orçamento científico | `Execução da primeira suite paga` | **Pendente** | 2 modelos frontier + 2 open-weight/local + fake; orçamento piloto explícito antes de escalar |
| [GATE-012](#gate-012) | Topologia de publicação de packages | `Release PyPI` | **Pendente** | Monorepo multi-package interno; publicar inicialmente uma distribuição agregadora e somente separar quando houver consumidores reais |


## GATE-001: Licença do kernel e substrato de regras

**Bloqueia:** M0 scaffold público  
**ADR vinculada:** `ADR-004`  
**Recomendação de arquitetura:** Apache-2.0 no kernel + substrato permissivo de regras atrás de port próprio  
**Enquanto pendente:** Bloquear publicação de pacote e criação de LICENSE.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Apache-2.0 + rules permissivo | Maior adoção, embedding comercial e neutralidade do kernel; mais trabalho inicial em bindings e PGN/SAN. |
| B | GPL-3.0 + python-chess | Entrega funcional mais rápida e biblioteca madura; copyleft influencia integração e distribuição do conjunto. |
| C | Dual repository / optional GPL plugin | Kernel permissivo e plugin GPL isolado; complexidade operacional e jurídica maior, fronteira precisa ser real. |

### Perguntas que o Mestre Mael precisa responder

- O kernel deve poder ser embutido em software proprietário?
- Aceitamos uma pequena ilha Rust/PyO3?
- PGN rico é requisito de v0.1 ou pode ser adiado?

### Registro da decisão

```yaml
id: GATE-001
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-002: Piso de Python e matriz de suporte

**Bloqueia:** Criação de pyproject e lockfile  
**ADR vinculada:** `ADR-003`  
**Recomendação de arquitetura:** Python >=3.13; CI em 3.13 e 3.14; desenvolvimento principal em 3.13 no primeiro ciclo  
**Enquanto pendente:** Não gerar uv.lock nem metadados finais de pacote.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | >=3.13, CI 3.13/3.14 | Acesso a recursos modernos e matriz pequena; exclui ambientes antigos. |
| B | >=3.12, CI 3.12-3.14 | Adoção maior; mais branches de compatibilidade e dependências. |
| C | Somente 3.13 no v0.1 | Menor superfície de teste; compromisso de suporte mais estreito. |

### Perguntas que o Mestre Mael precisa responder

- A adoção por laboratórios com ambientes conservadores é prioridade imediata?
- A extensão Rust precisa publicar wheels para quais versões?

### Registro da decisão

```yaml
id: GATE-002
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-003: Retenção padrão de prompts, responses e reasoning

**Bloqueia:** Defaults de artifact policy  
**ADR vinculada:** `ADR-036`  
**Recomendação de arquitetura:** Captura integral local privada; export público exige política explícita de derivação/redação  
**Enquanto pendente:** Fake provider apenas; providers reais não podem executar.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Full-local, public-redacted | Máxima auditabilidade local com controle de publicação; exige redaction pipeline. |
| B | Metadata-only por padrão | Menor risco e custo; reduz reprodutibilidade e auditoria. |
| C | Full sempre | Mais simples cientificamente; pode violar termos, privacidade ou políticas de provider. |

### Perguntas que o Mestre Mael precisa responder

- Quais providers permitem redistribuição?
- Reasoning oculto ou encrypted content será persistido?
- Qual teto de retenção local?

### Registro da decisão

```yaml
id: GATE-003
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-004: Nome do CLI público

**Bloqueia:** Publicação do entry point  
**ADR vinculada:** `ADR-037`  
**Recomendação de arquitetura:** Comando canônico `zugzwang`; alias curto `zgw` quando não houver colisão  
**Enquanto pendente:** Usar `python -m zugzwang_cli` internamente sem promessa pública.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | zugzwang + zgw | Descoberta semântica e ergonomia; dois entry points. |
| B | zgw apenas | Curto e eficiente; menos encontrável. |
| C | zug apenas | Curto, mas colisões e ambiguidade maiores. |

### Perguntas que o Mestre Mael precisa responder

- O pacote PyPI terá o mesmo nome?
- Queremos reservar `zugzwang` para produto maior?

### Registro da decisão

```yaml
id: GATE-004
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-005: Redistribuição de outputs e artefatos de providers

**Bloqueia:** Export público de bundles reais  
**ADR vinculada:** `ADR-040`  
**Recomendação de arquitetura:** Registry de políticas por provider/modelo + confirmação explícita antes de export público  
**Enquanto pendente:** Bundle marcado `private_only`; export externo bloqueado.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Registry advisory + operator acknowledgement | Prático e auditável; registry precisa de manutenção. |
| B | Nunca redistribuir raw | Seguro por padrão; papers ficam menos reproduzíveis. |
| C | Política por projeto sem registry | Flexível; decisões ficam dispersas e inconsistentes. |

### Perguntas que o Mestre Mael precisa responder

- Quais artefatos são necessários para claims públicos?
- Hashes e métricas derivadas bastam em alguns regimes?

### Registro da decisão

```yaml
id: GATE-005
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-006: Aquisição e distribuição do Stockfish

**Bloqueia:** UX do evaluator Stockfish  
**ADR vinculada:** `ADR-039`  
**Recomendação de arquitetura:** Binário fornecido pelo usuário no v0.1; downloader separado e juridicamente auditado depois  
**Enquanto pendente:** Somente fake UCI e evaluator sem engine.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | User-provided executable | Pouco risco e pouca automação. |
| B | Downloader oficial opcional | Melhor UX; precisa verificar plataforma, hash, licença e source offer. |
| C | Redistribuir binários | UX máxima; maior obrigação de compliance e release engineering. |

### Perguntas que o Mestre Mael precisa responder

- O primeiro público alvo tolera configuração manual?
- Quais OS/arquiteturas precisam de suporte?

### Registro da decisão

```yaml
id: GATE-006
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-007: Estabilidade inicial da API de plugins

**Bloqueia:** Expectativa pública de compatibilidade  
**ADR vinculada:** `ADR-043`  
**Recomendação de arquitetura:** Experimental até 0.3; compatibility window de uma minor; contracts explicitamente versionados  
**Enquanto pendente:** Plugins first-party apenas, com warning de API instável.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Experimental pre-0.3 | Permite aprender; plugins externos precisam pinning. |
| B | Estável desde 0.1 | Adoção mais confortável; congela erros cedo. |
| C | Sem plugins externos no v0.1 | Reduz escopo; posterga validação arquitetural. |

### Perguntas que o Mestre Mael precisa responder

- Há parceiros externos já esperando adapters?
- Quanto churn de schema aceitamos?

### Registro da decisão

```yaml
id: GATE-007
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-008: Escopo de variantes enxadrísticas no primeiro release

**Bloqueia:** Contrato do environment  
**ADR vinculada:** `ADR-042`  
**Recomendação de arquitetura:** Standard chess como happy path; variant_id no contrato; Chess960 apenas como capability futura  
**Enquanto pendente:** Standard only; outros variant IDs rejeitados.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Standard only, contracts variant-ready | Menor implementação e sem lock-in. |
| B | Standard + Chess960 no v0.1 | OOD útil desde cedo; eleva regras, test matrix e PGN. |
| C | Framework genérico de board games | Maior mercado aparente; dilui a ciência e o 80/20. |

### Perguntas que o Mestre Mael precisa responder

- Chess960 é requisito do primeiro paper?
- O rules substrate escolhido o suporta sem custo grande?

### Registro da decisão

```yaml
id: GATE-008
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-009: Governança do registry de custos

**Bloqueia:** Claims econômicos  
**ADR vinculada:** `ADR-041`  
**Recomendação de arquitetura:** Snapshots manuais versionados por experimento; provider usage é fonte de verdade quando disponível  
**Enquanto pendente:** Registrar usage e `cost_status=unknown`; proibir claim USD.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Snapshot manual versionado | Reproduzível; manutenção humana. |
| B | Preço online no runtime | Atual; não reproduzível e adiciona rede. |
| C | Sem custo USD, só tokens | Simples; perde comparação econômica entre providers. |

### Perguntas que o Mestre Mael precisa responder

- Custos são outcome primário no primeiro paper?
- Como representar discounts, cache e planos fechados?

### Registro da decisão

```yaml
id: GATE-009
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-010: Idioma canônico da documentação

**Bloqueia:** Política de contribuição internacional  
**ADR vinculada:** `ADR-038`  
**Recomendação de arquitetura:** README e contrato público em inglês; engenharia canônica inicialmente em PT-BR; tradução progressiva com source-of-truth explícito  
**Enquanto pendente:** Política atual deste foundation pack.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | English public, PT-BR engineering canonical | Velocidade do time e alcance público; dois níveis de documentação. |
| B | Tudo em inglês | Maior colaboração externa; maior custo de autoria para o operador. |
| C | Tudo bilíngue | Inclusivo; quase duplica manutenção e cria drift. |

### Perguntas que o Mestre Mael precisa responder

- Qual público de contribuição nos primeiros três meses?
- Quais docs precisam de paridade obrigatória?

### Registro da decisão

```yaml
id: GATE-010
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-011: Matriz inaugural de modelos e orçamento científico

**Bloqueia:** Execução da primeira suite paga  
**ADR vinculada:** `none`  
**Recomendação de arquitetura:** 2 modelos frontier + 2 open-weight/local + fake; orçamento piloto explícito antes de escalar  
**Enquanto pendente:** Executar somente fake e smoke tests locais.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Matriz compacta heterogênea | Boa cobertura por custo moderado. |
| B | Somente frontier APIs | Entrega rápida; baixa reprodutibilidade e custo maior. |
| C | Somente open-weight | Reprodutível; perde comparação com fronteira. |

### Perguntas que o Mestre Mael precisa responder

- Qual teto total em USD?
- Quais snapshots exatos estão acessíveis?
- Existe compute local suficiente?

### Registro da decisão

```yaml
id: GATE-011
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.

## GATE-012: Topologia de publicação de packages

**Bloqueia:** Release PyPI  
**ADR vinculada:** `ADR-045`  
**Recomendação de arquitetura:** Monorepo multi-package interno; publicar inicialmente uma distribuição agregadora e somente separar quando houver consumidores reais  
**Enquanto pendente:** Sem publicação PyPI; editable workspace apenas.

| Opção | Escolha | Impacto direto e indireto |
|---|---|---|
| A | Distribuição agregadora + packages internos | Instalação simples; boundaries preservadas no source. |
| B | Cada package publicado | Composição fina; versionamento e release mais complexos. |
| C | Single package físico | Menor setup; boundaries ficam mais sociais que mecânicas. |

### Perguntas que o Mestre Mael precisa responder

- Há consumidores que querem apenas `core`?
- Qual overhead de release aceitamos?

### Registro da decisão

```yaml
id: GATE-012
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```

O agente responsável deve atualizar `DECISIONS.yaml`, a ADR vinculada, a traceability matrix e qualquer template de scaffold afetado. A ausência de resposta nunca autoriza a opção recomendada automaticamente.



## Decision packet: GATE-011 — Matriz inaugural de modelos e orçamento científico

### Contexto

A Research Suite 0.1 (14 condições × 10 posições congeladas) está pronta para
execução. O bloco REP-001 RGB/MM-002 exige um modelo com visão; o
`opencode-go/deepseek-v4-flash` tem `attachment=false`. Spike real confirmou
que `opencode-go/mimo-v2.5` lê o tabuleiro via FilePart data URL e jogou
lance legal no e2e.

### Fato relevante

Ambos os modelos candidatos estão na assinatura OpenCode Go do operador —
o custo marginal da execução é zero além da assinatura já paga. Stockfish 18
é local (GATE-006).

### Recomendação

Matriz inaugural:
- texto: `opencode-go/deepseek-v4-flash` (todas as condições textuais)
- imagem: `opencode-go/mimo-v2.5` (REP-001 RGB/FEN+RGB, MM-002)
- orçamento piloto: ~210 calls na assinatura existente; full batch n≥24 fica
  para depois da análise do piloto (n=10).

Alternativa B: qwen3-vl-30b via OpenRouter (custo por token adicional).
Alternativa C: adiar RGB.

### Limitação registrada

Modelo × condição é confundido para visão (não comparamos modelos entre si;
comparações são dentro de bloco, por posição pareada).

### Pergunta ao operador

Ratifica `deepseek-v4-flash` + `mimo-v2.5` (assinatura OpenCode Go) como a
matriz inaugural da suite 0.1 com orçamento piloto de ~210 calls?

### Registro

```yaml
id: GATE-011
selected_option: null
rationale: null
approved_by: null
selected_at: null
revisit_trigger: null
```


## Ordem recomendada de decisão

`GATE-001 → GATE-002 → GATE-004 → GATE-003 → GATE-006 → GATE-008 → GATE-007 → GATE-010 → GATE-009 → GATE-005 → GATE-011 → GATE-012`

Os quatro primeiros liberam o scaffold sem comprometer pesquisa paga. Os demais podem ser ratificados antes do milestone que bloqueiam.
