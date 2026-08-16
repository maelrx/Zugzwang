---
name: implement-provider-adapter
description: Add or update a model provider/backend adapter with explicit capabilities, raw evidence, normalized requests/responses, errors, usage, and no hidden agency.
---

# Implement provider adapter

## Read first

- `docs/protocol/PROVIDER_CONTRACT.md`;
- `docs/architecture/PROVIDER_ARCHITECTURE.md`;
- `docs/engineering/PROVIDER_ADAPTER_GUIDE.md`;
- retention and redistribution gates.

## Workflow

1. Confirm provider terms and artifact policy are compatible with intended tests.
2. Create capability matrix with `native`, `emulated`, `unsupported`, `unknown`.
3. Implement canonical request lowering without mutating semantic content silently.
4. Capture provider/model identifiers and request metadata.
5. Normalize response while preserving raw bytes/JSON under policy.
6. Map errors into timeout, throttling, transport, refusal, invalid request and unknown outcome.
7. Extract reported usage; keep missing fields unknown.
8. Disable SDK retries/fallbacks or surface each attempt explicitly.
9. Add golden fixtures for text, structured output, images, tools, refusal and failures.
10. Pass the common backend contract suite offline.

## Forbidden

- model fallback;
- memory or agent loop;
- tool execution;
- unrecorded prompt rewrite;
- pricing network lookup;
- unsupported modality dropped silently;
- estimated tokens marked as provider-reported.

## Handoff

Include capability table, exact SDK/version, terms note, fixture provenance, unsupported behaviors and any emulation that changes experimental interpretation.
