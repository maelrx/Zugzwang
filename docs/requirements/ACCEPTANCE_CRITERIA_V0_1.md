# Critérios de aceitação v0.1

O v0.1 está concluído somente quando todos os itens abaixo possuem evidência automatizada ou um waiver aprovado por ADR.

## Installation and doctor

- [ ] CLI instala em ambiente limpo.
- [ ] `doctor` valida Python, SQLite fixo, filesystem, database, plugins e engine opcional.
- [ ] `doctor --json` possui schema estável.
- [ ] nenhum secret aparece na saída.

## Manifests and planning

- [ ] source YAML strict validation.
- [ ] resolved JSON canonical artifact.
- [ ] factor product/zip deterministic IDs.
- [ ] capabilities resolved before paid calls.
- [ ] human-gated unresolved settings fail with actionable message.
- [ ] dry plan shows episodes, calls, cost ceiling and incompatibilities.

## Runtime

- [ ] fake provider executes offline.
- [ ] R0-R3 run end to end.
- [ ] bounded concurrency and persistence backpressure.
- [ ] SIGINT creates safe checkpoint.
- [ ] resume never repeats committed action.
- [ ] outcome-unknown provider call is not blindly retried.
- [ ] finalize is idempotent.

## Chess

- [ ] state includes all standard-chess rule fields.
- [ ] UCI canonical action.
- [ ] no illegal action applied.
- [ ] MoveSelection, StateReconstruction and FullGame.
- [ ] random legal and UCI opponent.
- [ ] FEN, ASCII, history and image renderers.
- [ ] legal action hash reproducible.
- [ ] strict PGN mainline export.

## Providers

- [ ] deterministic fake.
- [ ] direct OpenAI-compatible contract smoke.
- [ ] Pydantic AI Direct adapter contract smoke.
- [ ] provider capability mismatch fails before run.
- [ ] canonical and lowered request artifacts linked.
- [ ] raw response policy recorded.
- [ ] retries/fallback/routing never hidden.

## Multimodal and knowledge

- [ ] image bytes are CAS artifacts.
- [ ] renderer metadata complete.
- [ ] no silent image-to-text fallback.
- [ ] static KnowledgePacket validates.
- [ ] packet content hash enters condition identity.
- [ ] H and K effective classes computed.
- [ ] protocol violation produced for undeclared impact.

## Persistence and bundles

- [ ] SQLite WAL and one-writer tests.
- [ ] SQLite minimum safe version enforced.
- [ ] artifact-before-reference crash test.
- [ ] run bundle contains manifests, events, artifacts, tables and checksums.
- [ ] import validates paths, hashes and schemas.
- [ ] imported bundle re-evaluates offline.
- [ ] Parquet queryable by DuckDB.

## Evaluation

- [ ] Stockfish is post-hoc in default protocols.
- [ ] binary/NNUE/config provenance.
- [ ] metrics append by version.
- [ ] parse, illegal and legal blunder separated.
- [ ] WDL/CP loss and operational metrics.
- [ ] paired reporter and uncertainty.
- [ ] report prints H/K/R/O/B/D profile.

## Quality

- [ ] offline CI has no provider/network dependency.
- [ ] unit, property, contract, integration, fault and architecture tests.
- [ ] Ruff and strict typing.
- [ ] schema compatibility fixtures.
- [ ] SBOM/lock export in release.
- [ ] docs validation.
- [ ] no unresolved blocking human gate.
