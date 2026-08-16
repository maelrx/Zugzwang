# Product Requirements Document

**Produto:** Zugzwang Research Kernel  
**Fase:** foundation / pre-scaffold  
**Primeiro domínio:** standard chess  
**Interface inicial:** CLI  
**Modo operacional:** local-first, single host  
**Público primário:** pesquisadores e engenheiros de sistemas agentic

## 1. Resultado de produto

O usuário fornece um manifesto, o kernel resolve e valida a condição, executa episodes, registra evidência e produz um bundle reavaliável.

```text
source manifest
→ resolved manifest
→ execution plan
→ run / episodes / steps / attempts
→ event stream + artifacts + projections
→ post-hoc evaluation
→ portable bundle + analytical tables
```

## 2. Jobs to be done

### JTBD-01: comparar interfaces

“Quero medir FEN, PGN, ASCII, imagem e combinações sem alterar outras variáveis.”

### JTBD-02: comparar harnesses

“Quero saber se legal moves, repair ou structured reasoning melhoram o sistema, separando validade de qualidade.”

### JTBD-03: comparar conhecimento

“Quero testar uma knowledge packet correta contra placebo, pacote errado e baseline, com mesmo token budget.”

### JTBD-04: comparar providers e modelos

“Quero executar o mesmo protocolo em APIs comerciais e servidores locais sem reescrever o experimento.”

### JTBD-05: publicar evidência

“Quero entregar logs, manifests, snapshots, métricas e checksums que outro pesquisador consiga auditar.”

### JTBD-06: retomar execução cara

“Quero interromper uma bateria e continuar do primeiro step não commitado, sem duplicar ações ou custos.”

### JTBD-07: reavaliar offline

“Quero aplicar uma nova versão da métrica ou outro budget de Stockfish a um bundle já concluído.”

## 3. Escopo v0.1

### Incluído

- manifestos YAML estritos compilados para JSON canônico;
- experiment planning e deterministic IDs;
- CLI e JSON output estável;
- SQLite WAL operacional;
- filesystem CAS;
- event stream append-only;
- resume por state machines explícitas;
- fake provider offline;
- provider OpenAI-compatible direto;
- adapter Pydantic AI Direct;
- typed multimodal content parts;
- static knowledge packets;
- R0, R1, R2 e R3;
- MoveSelection, StateReconstruction e FullGame;
- random legal e UCI opponent;
- Stockfish pós-hoc;
- Parquet + DuckDB;
- bundle export/import;
- H/K classification e protocol violation detection;
- experiment templates REP-001, GROUND-001, SKILL-001, MM-001, MM-002 e DEMO-001.

### Excluído

- treino, SFT ou RLVR;
- Web UI;
- API remota multiusuário;
- Postgres, Redis e filas distribuídas;
- vector database;
- MCP como protocolo interno;
- engine live por default;
- public leaderboard;
- automatic model routing;
- hidden fallback;
- arbitrary code execution;
- provider price auto-scraping;
- Chess960 no happy path inicial.

## 4. Personas

Veja [PERSONAS_AND_JOBS.md](PERSONAS_AND_JOBS.md).

## 5. Functional slices

### Slice A: constitution

Contracts, ADRs, schemas, package boundaries, error model, test catalog.

### Slice B: deterministic local runtime

Create, validate, plan, execute fake episodes, checkpoint, resume, finalize.

### Slice C: formal chess environment

Canonical state, legal transition, tasks, notation codecs, UCI boundary.

### Slice D: model backends and strategies

Capability negotiation, exact request artifacts, explicit retry semantics, R0-R3.

### Slice E: evaluation and bundles

Versioned metrics, post-hoc engine, Parquet, DuckDB, export/import.

### Slice F: scientific suite

Paired conditions, preregistration, experiment cards, reports, cost-strength curves.

## 6. User experience

The CLI must support two modes:

- human-readable Rich output;
- stable JSON/JSONL for scripts and future API adapters.

Core commands:

```text
zgw doctor
zgw validate <manifest>
zgw plan <manifest>
zgw run <manifest>
zgw resume <run-id>
zgw status <run-id>
zgw cancel <run-id>
zgw evaluate <run-id|bundle>
zgw bundle export <run-id>
zgw bundle import <path>
zgw report <run-id|bundle>
zgw plugins list
zgw schema export
```

`zgw` is provisional until `GATE-004`.

## 7. Success criteria

The release is useful when an independent contributor can implement a provider plugin and run the same experiment without modifying core; a second machine can import the bundle and reproduce all deterministic projections and post-hoc metrics; and the report makes assistance and protocol differences impossible to overlook.

## 8. Product risks

- scope collapse into a universal agent framework;
- attractive dashboards displacing protocol work;
- model/provider wrappers hiding retries;
- engine leakage;
- bundle sizes becoming unmanageable;
- premature public API promises;
- licensing locking out desired contributors;
- scientific vocabulary being reduced to marketing badges.

Mitigations are tracked in the [risk register](../roadmap/RISK_REGISTER.md).
