# Versioning and compatibility

## Independent version spaces

- software release;
- manifest schema;
- event types;
- bundle schema;
- plugin API;
- metric definitions;
- knowledge packet schema;
- experiment suite;
- renderer;
- provider profile.

Do not reuse one version number as a proxy for all.

## Pre-1.0

- breaking software changes allowed with changelog;
- persisted artifacts still require explicit readers/upcasters;
- public plugin API remains experimental unless ADR-043 says otherwise;
- no silent deletion of event fields.

## Compatibility policy

- unknown major: fail;
- newer minor: accept only when declared forward-compatible;
- patch: compatible bug fix;
- upcaster: raw bytes preserved, current projection generated;
- migration: never rewrites published bundle in place.

## Deprecation

A deprecation declares:

- replacement;
- first warned version;
- earliest removal;
- migration command;
- affected artifacts/plugins.
