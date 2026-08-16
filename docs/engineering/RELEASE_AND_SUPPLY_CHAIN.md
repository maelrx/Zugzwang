# Release e supply chain

## Release artifacts

- source archive;
- Python wheel(s) according to GATE-012;
- lockfile and exported dependency inventory;
- CycloneDX SBOM;
- JSON Schemas;
- migration/upcaster compatibility fixtures;
- checksums;
- signed tag/release provenance when infrastructure supports it;
- release notes and known limitations;
- fake demonstration bundle.

## Dependency policy

- direct dependency needs purpose, owner and alternative analysis;
- pin/lock exact transitive graph for releases;
- no runtime dependency solely for convenience if stdlib suffices;
- provider SDKs remain optional extras/plugins when possible;
- native dependency requires wheel/platform plan;
- GPL/AGPL dependencies require explicit license review.

## Build policy

- build from clean checkout;
- no secret or network-dependent code generation;
- schemas generated deterministically;
- source archive and wheel tested in clean environments;
- SBOM exported from the resolved lock;
- artifact checksums attached to release.

## Versioning

Version spaces are independent:

- package release;
- manifest schema;
- event schema;
- bundle schema;
- metric definitions;
- plugin API;
- experiment protocol.

A package patch may include a new metric version without mutating old metric semantics.

## Emergency release

Security or corruption fixes may bypass normal cadence, never evidence requirements. Release custodian documents affected versions, migration behavior and whether old bundles/runs remain trustworthy.
