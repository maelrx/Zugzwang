# Matriz de rastreabilidade

| Capability | Requirements | ADRs | Milestone | Primary tests |
|---|---|---|---|---|
| strict manifests | FR-002–006, NFR-012 | 008, 030 | M0/M1 | schema, golden, property |
| modular packages | NFR-006–007 | 002, 005–007 | M0 | architecture imports |
| durable runtime | FR-009–021 | 010–014, 019–020 | M1 | fault, resume, idempotency |
| formal chess | FR-022–032 | 004, 023–024, 042 | M2 | perft/conformance/property |
| providers | FR-012, 016–018 | 016–019 | M3 | provider contract matrix |
| multimodal | FR-056–059, NFR-021 | 033 | M3/M6 | image artifact/lowering/conflict |
| knowledge packets | FR-060–062 | 034–035 | M3/M6 | schema/placebo/taint |
| persistence | FR-033–040 | 012–015, 044 | M1/M4 | crash, migration, integrity |
| evaluation | FR-041–048 | 024–026 | M4 | engine fake/golden/idempotency |
| bundles | FR-036–038 | 014–015, 030 | M4 | export/import/tamper |
| security | FR-049–055, NFR-013/027/030 | 021, 028, 039–040 | M5 | threat fixtures |
| plugins | FR-007–008 | 022, 043 | M5 | discovery/API compatibility |
| experiments | FR-063–064 | 034–035 | M6 | paired planner/stat reporter |
| human gates | FR-068–070, NFR-026 | 003,004,036–043 | M0/release | decision validator |
