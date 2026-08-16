# Personas e jobs

## 1. Pesquisador de foundation models

**Precisa:** comparar interfaces, budgets, reasoning e multimodalidade.  
**Dor atual:** scripts ad hoc, APIs mutáveis, protocolo incompleto.  
**Valor:** condições versionadas, paired design, bundles e attribution.

## 2. Engenheiro de agentes

**Precisa:** saber se retries, tools e orchestration realmente ajudam.  
**Dor atual:** frameworks escondem semântica e custos.  
**Valor:** cada attempt, fallback e tool call aparece no event stream.

## 3. Autor de benchmark

**Precisa:** publicar suite viva e importar resultados.  
**Dor atual:** formato de saída e métricas incompatíveis.  
**Valor:** schemas, experiment cards, registries e bundle contract.

## 4. Autor de modelo ou provider

**Precisa:** integrar uma policy local ou API.  
**Dor atual:** reescrever game loops e relatórios.  
**Valor:** `ModelBackend` e plugin contracts estáveis.

## 5. Especialista em xadrez / curador

**Precisa:** construir knowledge packets e suites sem alterar runtime.  
**Dor atual:** conhecimento experto fica enterrado em prompts.  
**Valor:** pacote versionado, provenance, K-class e controles placebo/wrong-skill.

## 6. Revisor de reproducibilidade

**Precisa:** determinar o que um claim realmente mede.  
**Dor atual:** prompt, retries e engine settings ausentes.  
**Valor:** claims policy, checksums, resolved manifest e evidence graph.

## 7. Mantenedor do projeto

**Precisa:** evoluir contratos sem quebrar bundles antigos.  
**Dor atual:** schema drift e plugins acoplados.  
**Valor:** ADRs, semantic version spaces, upcasters e compatibility fixtures.

## 8. Futuro operador hosted

**Precisa:** coordenar múltiplos usuários e workers.  
**Dor futura:** transformar um CLI acoplado em serviço.  
**Preparação atual:** application services, repository ports, stable DTOs, cursorable events e artifact IDs.

O hosted não é usuário prioritário do v0.1. Ele influencia portas, não o runtime inicial.
