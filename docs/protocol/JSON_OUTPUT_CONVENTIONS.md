# JSON output conventions

- UTF-8;
- RFC 3339 UTC timestamps;
- snake_case fields;
- IDs as strings;
- money as decimal string plus currency when exact;
- durations as integer milliseconds or explicit unit;
- unknown as `null`, never zero;
- enums lowercase in JSON unless protocol taxonomy requires `R0/H2/K0`;
- arrays preserve semantic order;
- maps do not carry order semantics;
- raw bytes referenced by artifact;
- schema version at top-level;
- no secrets;
- no ANSI;
- errors use stable code;
- extensions namespaced under `extensions`.
