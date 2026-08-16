# Future API and Web UI

## What we prepare now

- application command/query services;
- Pydantic DTOs and JSON Schema;
- stable IDs;
- paged list queries;
- event cursors;
- artifact endpoints as ports;
- cancellation semantics;
- machine-readable CLI;
- immutable resolved manifests.

## What we do not build now

- FastAPI;
- SSE/WebSocket;
- auth;
- tenancy;
- browser rendering;
- React/Vite;
- Postgres;
- object storage;
- remote queue.

## Future shape

```text
Web UI
→ HTTP/SSE adapter
→ same application services
→ repository/artifact ports
```

The UI must never read SQLite or CAS layout directly.

## Trigger for API milestone

At least one:

- external consumer needs remote execution;
- multiple humans need shared runs;
- public benchmark needs a service;
- CLI machine output proves insufficient.

A dashboard desire alone is not a trigger.
