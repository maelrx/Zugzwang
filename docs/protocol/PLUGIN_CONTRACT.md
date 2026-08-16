# Plugin contract

## Entry point groups

```text
zugzwang.providers
zugzwang.environments
zugzwang.tasks
zugzwang.strategies
zugzwang.evaluators
zugzwang.reporters
zugzwang.codecs
zugzwang.tools
```

## Descriptor schema

```yaml
plugin_id:
plugin_version:
api_version:
kind:
distribution:
license:
capabilities:
config_schema:
trust:
```

## Rules

- IDs globally unique within kind.
- Import must not perform network calls.
- Discovery must not instantiate clients.
- Config uses Pydantic strict boundary models.
- Plugin exceptions map to kernel errors.
- No direct DB session.
- No direct CAS path assumptions.
- All artifacts go through `ArtifactStore`.
- Assistance impacts are declared by tools/evaluators.
- Distribution and version enter run snapshot.

## Compatibility

Pre-1.0 API may evolve, but exact compatibility range is declared. Contract fixtures are the executable specification.

## Third-party plugins

Run in-process and are trusted code in v0.1. Users receive a warning. No marketplace or auto-install exists.
