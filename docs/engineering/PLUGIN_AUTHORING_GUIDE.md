# Guia de autoria de plugins

## Plugin categories

- providers;
- environments;
- tasks;
- strategies;
- evaluators;
- reporters;
- codecs.

## Registration

Plugins use Python entry points under versioned groups such as `zugzwang.providers`. Discovery is local and side-effect-minimal. Import must not open network, start subprocess or read secrets.

## Metadata

```yaml
plugin:
  id: org.example.plugin
  version: 0.1.0
  api_version: 1
  license: Apache-2.0
  trust_level: third_party
  capabilities: []
  side_effects: []
```

## Rules

- depend on public contracts only;
- no database session or internal repository access;
- persist custom payloads through namespaced artifacts/events;
- validate config strictly;
- expose deterministic capability report;
- declare assistance impact for tools/evaluators;
- include offline contract tests and fixtures;
- do not monkeypatch runtime or global logging.

## Stability

Until GATE-007 and the corresponding release policy are ratified, third-party plugin compatibility is experimental. A plugin declares the supported API range and fails clearly outside it.
