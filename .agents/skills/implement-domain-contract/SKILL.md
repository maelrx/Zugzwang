---
name: implement-domain-contract
description: Implement or change a core domain value object, port, event, manifest model, or public protocol contract while preserving dependency direction and compatibility.
---

# Implement a domain contract

## Use when

The work changes canonical IDs, dataclasses, ports, events, manifests, content parts, errors or serialized protocol models.

## Read

- `docs/architecture/DOMAIN_MODEL.md`;
- `docs/architecture/DEPENDENCY_RULES.md`;
- `docs/protocol/VERSIONING.md`;
- related schema and ADR;
- nearest package `AGENTS.md`.

## Workflow

1. State the invariant and consumers before writing types.
2. Decide whether the type is internal domain, boundary DTO or persisted protocol.
3. Keep domain types free of SDK/DB/CLI/concrete-chess imports.
4. Model unknown, absent and zero as distinct where semantically relevant.
5. Add discriminators/schema versions for persisted unions.
6. Define explicit conversion at every adapter boundary.
7. Add equality, hashing, serialization and invalid-input tests.
8. Generate/update JSON Schema and examples.
9. Analyze backward compatibility and upcaster needs.
10. Update traceability matrix and public API inventory.

## Review questions

- Can two IDs be accidentally interchanged?
- Does serialization depend on Python implementation detail?
- Can an old artifact still be read?
- Did a provider or chess library type leak inward?
- Is every enum value forward-compatible by policy?
- Does the error expose retryability and outcome ambiguity?

## Stop conditions

Stop for ADR when the contract changes persisted meaning, package direction, public plugin API or a human-owned policy.
