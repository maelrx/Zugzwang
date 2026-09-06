# Documentation index

Current entry point: [repository status and integration queue](engineering/REPOSITORY_STATUS.md). Historical design documents do not supersede accepted gates or the current PR state.

The canonical documentation language for the foundation release is Portuguese, with an English public README. This policy is itself a human decision gate for later releases.

## Product

- [Vision](product/VISION.md)
- [Product Requirements Document](product/PRODUCT_REQUIREMENTS.md)
- [Scope and non-goals](product/SCOPE_AND_NON_GOALS.md)
- [Personas and jobs](product/PERSONAS_AND_JOBS.md)
- [Positioning and ecosystem](product/POSITIONING_AND_ECOSYSTEM.md)
- [Success metrics](product/SUCCESS_METRICS.md)
- [OSS and future hosted boundary](product/OSS_AND_FUTURE_HOSTED.md)
- [Naming and identity](product/NAMING_AND_IDENTITY.md)

## Research

- [Scientific foundations](research/SCIENTIFIC_FOUNDATIONS.md)
- [Literature map](research/LITERATURE_MAP.md)
- [Protocol taxonomy](research/PROTOCOL_TAXONOMY.md)
- [Representations and multimodality](research/REPRESENTATIONS_AND_MULTIMODALITY.md)
- [Experiment catalog v0.1](research/EXPERIMENT_CATALOG_V0_1.md)
- [Experimental design and statistics](research/EXPERIMENT_DESIGN_AND_STATISTICS.md)
- [Claims and evidence policy](research/CLAIMS_AND_EVIDENCE_POLICY.md)
- [Data, contamination, and splits](research/DATA_CONTAMINATION_AND_SPLITS.md)
- [Research agenda](research/RESEARCH_AGENDA.md)
- [Bibliography](research/BIBLIOGRAPHY.md)
- [Experiment card template](research/EXPERIMENT_CARD_TEMPLATE.md)
- [Evaluation corpus v0.1 spec](research/EVALUATION_CORPUS_V0_1.md)
- [Preregistration template](research/PREREGISTRATION_TEMPLATE.md)
- [Analysis plan template](research/ANALYSIS_PLAN_TEMPLATE.md)
- [Model matrix template](research/MODEL_MATRIX_TEMPLATE.md)
- [Cost and power planning](research/COST_AND_POWER_PLANNING.md)
- [Source note template](research/SOURCE_NOTE_TEMPLATE.md)

## Architecture

- [Master technical design](architecture/MASTER_TECHNICAL_DESIGN.md)
- [System design](architecture/SYSTEM_DESIGN.md)
- [C4 model](architecture/C4_MODEL.md)
- [Repository layout](architecture/REPOSITORY_LAYOUT.md)
- [Dependency rules](architecture/DEPENDENCY_RULES.md)
- [Domain model](architecture/DOMAIN_MODEL.md)
- [Runtime and state machines](architecture/RUNTIME_AND_STATE_MACHINES.md)
- [Data architecture](architecture/DATA_ARCHITECTURE.md)
- [Operational schema draft](architecture/OPERATIONAL_SCHEMA_DRAFT.md)
- [Provider architecture](architecture/PROVIDER_ARCHITECTURE.md)
- [Multimodal content model](architecture/MULTIMODAL_CONTENT_MODEL.md)
- [Strategies, tools, and knowledge](architecture/STRATEGIES_TOOLS_AND_KNOWLEDGE.md)
- [Chess domain](architecture/CHESS_DOMAIN.md)
- [Evaluation architecture](architecture/EVALUATION_ARCHITECTURE.md)
- [Plugin system](architecture/PLUGIN_SYSTEM.md)
- [Security threat model](architecture/SECURITY_THREAT_MODEL.md)
- [Observability and provenance](architecture/OBSERVABILITY_AND_PROVENANCE.md)
- [Future API and Web UI](architecture/FUTURE_API_AND_WEBUI.md)
- [Error model](architecture/ERROR_MODEL.md)
- [Performance budgets](architecture/PERFORMANCE_BUDGETS.md)
- [Technology radar](architecture/TECHNOLOGY_RADAR.md)
- [Architecture alternatives matrix](architecture/ALTERNATIVES_MATRIX.md)
- [Legality gateway](architecture/LEGALITY_GATEWAY.md)
- [Decision evidence](architecture/DECISION_EVIDENCE.md)
- [SearchWorkspace](architecture/SEARCH_WORKSPACE.md)
- [Search Memory](architecture/SEARCH_MEMORY.md)
- [Model-only search](architecture/MODEL_ONLY_SEARCH.md)
- [Evaluation firewall](architecture/EVALUATION_FIREWALL.md)

## Requirements

- [Functional requirements](requirements/FUNCTIONAL_REQUIREMENTS.md)
- [Non-functional requirements](requirements/NONFUNCTIONAL_REQUIREMENTS.md)
- [Acceptance criteria v0.1](requirements/ACCEPTANCE_CRITERIA_V0_1.md)
- [Traceability matrix](requirements/TRACEABILITY_MATRIX.md)
- [Open questions](requirements/OPEN_QUESTIONS.md)

## Protocol specifications

- [Manifest specification](protocol/MANIFEST_SPEC.md)
- [Event model](protocol/EVENT_MODEL.md)
- [Run bundle specification](protocol/RUN_BUNDLE_SPEC.md)
- [Provider contract](protocol/PROVIDER_CONTRACT.md)
- [Plugin contract](protocol/PLUGIN_CONTRACT.md)
- [Knowledge packet specification](protocol/KNOWLEDGE_PACKET_SPEC.md)
- [Content parts specification](protocol/CONTENT_PARTS_SPEC.md)
- [Metric specification](protocol/METRIC_SPEC.md)
- [CLI specification](protocol/CLI_SPEC.md)
- [Error codes](protocol/ERROR_CODES.md)
- [Versioning and compatibility](protocol/VERSIONING.md)
- [JSON output conventions](protocol/JSON_OUTPUT_CONVENTIONS.md)

## Engineering

- [Codex agent operating model](engineering/CODEX_AGENT_OPERATING_MODEL.md)
- [Development workflow](engineering/DEVELOPMENT_WORKFLOW.md)
- [Coding standards](engineering/CODING_STANDARDS.md)
- [Test strategy](engineering/TEST_STRATEGY.md)
- [CI quality gates](engineering/CI_QUALITY_GATES.md)
- [Release and supply chain](engineering/RELEASE_AND_SUPPLY_CHAIN.md)
- [Migration policy](engineering/MIGRATION_POLICY.md)
- [Documentation governance](engineering/DOCUMENTATION_GOVERNANCE.md)
- [Code review checklist](engineering/CODE_REVIEW_CHECKLIST.md)
- [Provider adapter guide](engineering/PROVIDER_ADAPTER_GUIDE.md)
- [Plugin authoring guide](engineering/PLUGIN_AUTHORING_GUIDE.md)
- [Benchmark execution playbook](engineering/BENCHMARK_EXECUTION_PLAYBOOK.md)
- [Database migration guide](engineering/DATABASE_MIGRATION_GUIDE.md)
- [Work Order template](engineering/WORK_ORDER_TEMPLATE.md)
- [Handoff template](engineering/HANDOFF_TEMPLATE.md)
- [Codex skills catalog](../AGENTS.md)

## Decisions and ADRs

- [Mestre Mael decision console](decisions/HUMAN_DECISION_GATES.pt-BR.md)
- [Machine-readable decisions](decisions/DECISIONS.yaml)
- [ADR index](adr/README.md)
- [ADR template](adr/ADR-TEMPLATE.md)
- [Candidate decision backlog](adr/CANDIDATE_DECISIONS.md)
- [Decision record template](decisions/DECISION_RECORD_TEMPLATE.md)
- [Decision log](decisions/DECISION_LOG.md)
- [ADR-048 RulesKernel versus LegalityGateway](adr/ADR-048-ruleskernel-vs-legality-gateway.md)
- [ADR-049 Legality exposure profiles](adr/ADR-049-legality-exposure-profiles.md)
- [ADR-050 Capability leases](adr/ADR-050-capability-leases.md)
- [ADR-051 Decision evidence model](adr/ADR-051-decision-evidence-model.md)
- [ADR-052 Raw wire retention](adr/ADR-052-raw-wire-retention.md)
- [ADR-053 Reasoning telemetry](adr/ADR-053-reasoning-telemetry.md)
- [ADR-054 EvaluationRun separation](adr/ADR-054-evaluation-run-separation.md)
- [ADR-055 SearchWorkspace immutable DAG](adr/ADR-055-searchworkspace-immutable-dag.md)
- [ADR-056 Endogenous Search Memory](adr/ADR-056-endogenous-search-memory.md)
- [ADR-057 R6 model-only search](adr/ADR-057-r6-model-only-search.md)
- [ADR-058 Post-hoc engine firewall](adr/ADR-058-posthoc-engine-firewall.md)
- [ADR-059 R5 multi-agent review por lance](adr/ADR-059-multi-agent-review.md)
- [ADR-060 Legal tree e ablação de memória por episódio](adr/ADR-060-turn-scoped-legality-and-memory-ablation.md)
- [ADR-061 Bateria controlada de agente único](adr/ADR-061-single-agent-tree-hypothesis-battery.md)

## Roadmap

- [Roadmap](roadmap/ROADMAP.md)
- [Dependency sequence](roadmap/DEPENDENCY_SEQUENCE.md)
- [Bootstrap backlog](roadmap/BOOTSTRAP_BACKLOG.md)
- [Risk register](roadmap/RISK_REGISTER.md)
- [M0](roadmap/M0-CONSTITUTION.md)
- [M1](roadmap/M1-LOCAL-RUNTIME.md)
- [M2](roadmap/M2-CHESS-DOMAIN.md)
- [M3](roadmap/M3-PROVIDERS-AND-STRATEGIES.md)
- [M4](roadmap/M4-EVALUATION-AND-BUNDLES.md)
- [M5](roadmap/M5-HARDENING.md)
- [M6](roadmap/M6-SCIENTIFIC-SUITE.md)
- [Release criteria](roadmap/RELEASE_CRITERIA.md)
- [Future horizons](roadmap/FUTURE_HORIZONS.md)

## Governance and source provenance

- [Source provenance](governance/SOURCE_PROVENANCE.md)
- [Research update policy](governance/RESEARCH_UPDATE_POLICY.md)
- [Decision ownership](governance/DECISION_OWNERSHIP.md)
- [Document status](governance/DOCUMENT_STATUS.md)
- [Publication policy](governance/PUBLICATION_POLICY.md)
- [Claim register template](governance/CLAIM_REGISTER_TEMPLATE.md)

## Machine-readable contracts and examples

- [Schema index](../schemas/README.md)
- [Example manifests and knowledge packets](../examples/README.md)
- [Foundation manifest](../FOUNDATION_MANIFEST.yaml)
- [Source archive manifest](../archive/source-material/MANIFEST.yaml)

## Repository operations

- [Root agent instructions](../AGENTS.md)
- [Contributing](../CONTRIBUTING.md)
- [Governance](../GOVERNANCE.md)
- [Security](../SECURITY.md)
- [Foundation report](../FOUNDATION_REPORT.md)

## Execution reports

- [Real pipeline — MuseSpark 1.3 Free and Stockfish](reports/REAL-PIPELINE-2026-09-04.md)
- [Bateria MuseSpark 1.3 contra Stockfish](reports/MUSESPARK-STOCKFISH-BATTERY-2026-09-04.md)
- [Validacao real pos-mudancas](reports/REAL-VALIDATION-2026-09-04.md)
- [Relatorio completo da run R5 multiagente](reports/R5-MULTI-AGENT-RUN-2026-09-04.md)
- [Run R7 legal tree e memoria persistida](reports/R7-LEGAL-TREE-MEMORY-RUN-2026-09-04.md)
- [Partida H3 do agente unico — relatorio cientifico](reports/R7-SINGLE-AGENT-TREE-GAME-H3-2026-09-05.md)
