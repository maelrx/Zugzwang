# Strategies, tools e knowledge

## 1. DecisionStrategy

A strategy coordinates model calls and returns a `DecisionTrace`.

```python
class DecisionStrategy(Protocol):
    async def decide(
        self,
        observation: Observation,
        budget: InferenceBudget,
        services: StrategyServices,
    ) -> DecisionTrace: ...
```

Strategies own orchestration. Backends own transport.

## 2. Initial strategies

- `R0DirectStrategy`;
- `R1GroundedStrategy`;
- `R2RepairStrategy`;
- `R3StructuredStrategy`.

No generic graph DSL is required.

## 3. Tool descriptor

```yaml
tool_id:
input_schema:
output_schema:
determinism:
side_effects:
network_scope:
filesystem_scope:
trust:
cache_policy:
assistance_impact_h:
knowledge_impact_k:
```

Tools never receive arbitrary filesystem access. Model-generated code execution is out of scope.

## 4. Verifiers

Separate:

- format parser `H0`;
- rules/legal verifier `H1`;
- canonical environment `H2`;
- action grounding `H3`;
- engine critic `H5`.

A verifier result cannot be called neutral if it contains move quality.

## 5. KnowledgePacket

Static domain data injected into a strategy.

```yaml
packet_id:
version:
scope:
claims:
applicability:
contraindications:
provenance:
license:
token_budget:
leakage_class:
knowledge_class:
```

Packets are content artifacts and enter the condition hash.

## 6. Why not RAG initially

RAG introduces corpus, indexing, embedding, chunking, retrieval, reranking, freshness, licensing and contamination variables. `SKILL-001` only requires static packet injection. Retrieval enters later as `K6/R7`.

## 7. MCP

MCP may be an adapter for external tools. Internal semantics remain the Zugzwang `Tool` contract because assistance, side effects and provenance are mandatory. Discovery does not imply authorization.

## 8. Memory

v0.1 supports explicit history policies:

- none;
- full transcript;
- last N plies;
- state snapshots;
- generated summary as an artifact.

There is no hidden long-term memory.
