# CLI specification

**Provisional command:** `zgw`

## Design rules

- CLI is a thin adapter;
- commands call application services;
- human and JSON output separated;
- stable exit codes;
- no interactive prompt in CI mode;
- secrets never echoed;
- `--dry-run` does not call providers;
- every mutation prints resulting ID.

## Commands

```text
zgw init
zgw doctor
zgw validate
zgw plan
zgw run
zgw resume
zgw pause
zgw cancel
zgw status
zgw events
zgw evaluate
zgw report
zgw bundle export
zgw bundle import
zgw plugins list
zgw plugins inspect
zgw schema export
zgw artifacts verify
zgw gc
zgw version
```

## Common flags

```text
--workspace
--json
--quiet
--log-level
--no-color
--set <path=value>
--retention-policy
--budget-max-usd
```

## Output envelope

```json
{
  "schema_version": "0.1.0",
  "command": "plan",
  "ok": true,
  "result": {},
  "warnings": [],
  "error": null
}
```

## Exit code families

- 0 success;
- 2 usage/config;
- 3 capability;
- 4 provider/runtime;
- 5 protocol/data;
- 6 security;
- 7 compatibility;
- 130 interrupted.

Exact mapping in `ERROR_CODES.md`.

## Naming gate

`zgw` is concise but opaque. `zugzwang` is discoverable but long. The accepted CLI may expose `zugzwang` with `zgw` alias. Human decision required.
