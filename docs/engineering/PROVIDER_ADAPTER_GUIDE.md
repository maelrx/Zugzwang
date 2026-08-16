# Guia de implementação de provider adapter

## Contract boundary

An adapter converts one canonical `ModelRequest` into one provider request and returns one `ModelResponse`. It may perform transport-level handling only when every attempt is surfaced to the runtime.

## Mandatory deliverables

- capability inspector;
- request lowering;
- response normalization;
- raw request/response artifact policy;
- usage extraction and unknown semantics;
- timeout/error taxonomy mapping;
- provider/model fingerprint;
- structured-output behavior;
- multimodal content handling;
- golden fixtures;
- contract tests;
- license/terms note.

## Forbidden behavior

- hidden automatic retry;
- fallback to another model;
- tool loop;
- memory/history mutation outside request;
- unrecorded prompt rewriting;
- pricing lookup over network during a run;
- silently dropping unsupported content part;
- reporting estimated usage as provider-reported usage.

## Capability statuses

`native`, `emulated`, `unsupported`, `unknown`.

Emulation changes the condition and must emit an event. An adapter that parses free text into JSON is not equivalent to native constrained structured output.

## Test vectors

- text-only;
- strict structured output;
- image input;
- tool schema without execution;
- empty/partial usage;
- refusal/content filter;
- provider 429/5xx;
- timeout before/after headers;
- malformed stream;
- unknown model.
