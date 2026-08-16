# Plugin system

## Discovery

Python entry points:

```text
zugzwang.providers
zugzwang.environments
zugzwang.strategies
zugzwang.evaluators
zugzwang.reporters
zugzwang.codecs
zugzwang.tools
```

## Descriptor

Every plugin exposes metadata before activation:

- plugin ID;
- version;
- API version;
- capabilities;
- license;
- trust requirements;
- dependencies;
- entry point;
- configuration schema.

## Lifecycle

1. discover metadata;
2. validate API compatibility;
3. list without importing heavy implementation when possible;
4. activate explicitly;
5. snapshot distribution/version/hash;
6. execute behind port;
7. record failures as plugin errors.

## Trust

v0.1 plugins run in-process and are trusted code. The CLI must warn for third-party plugins. Sandboxing is not promised.

## Stability

Until ADR-043 is accepted:

- public plugin API is experimental;
- first-party plugins can evolve together;
- third-party compatibility requires exact minor ranges;
- breaking changes need migration notes and fixtures.

## No auto-install

The kernel never installs a plugin because a manifest names it. Missing plugins fail validation with an actionable error.
