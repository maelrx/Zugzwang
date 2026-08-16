# Arquitetura de providers

## Contract

```python
class ModelBackend(Protocol):
    async def inspect_capabilities(self, model: ModelRef) -> CapabilityReport: ...

    async def infer(
        self,
        request: ModelRequest,
        context: CallContext,
    ) -> ModelResponse: ...
```

A backend performs one inference. It does not own strategy, memory, retries, tools, routing or fallback.

## Canonical request

- model ref;
- ordered messages;
- typed content parts;
- output contract;
- tool declarations;
- inference settings;
- timeout;
- idempotency hint;
- metadata;
- artifact refs.

## Canonical response

- normalized content parts;
- tool-call proposals;
- finish reason;
- usage;
- provider request ID;
- latency;
- raw response artifact;
- capability deviations;
- outcome status.

## Initial adapters

### Pydantic AI Direct

Use low-level model request functionality for schema/transport translation. Do not use `Agent`, fallback, durable execution, tool loop or memory as kernel semantics.

Pydantic AI V2 is stable, but its version policy allows new message parts and optional fields in minor releases. Consume defensively and pin through the lockfile.

### Direct OpenAI-compatible

`httpx` adapter for local servers and provider dialects. “Compatible” is treated as a profile with conformance tests, not an identity claim.

### Fake backend

Deterministic scripted responses, errors, latency and usage for offline tests.

### Optional LiteLLM bridge

Long-tail convenience only. Routing, retry and fallback must be disabled or surfaced as events.

## Capability model

```text
text_input
image_input
structured_output
tool_calling
streaming
seed
reasoning_control
usage_reporting
logprobs
prompt_caching
batch
idempotency_key
```

Manifest declares required/preferred capabilities and `on_unsupported`.

## Retry layers

- transport retry before response certainty;
- throttle retry;
- provider error retry;
- parse repair;
- legality repair;
- strategic resample;
- fallback model.

Each layer has a different scientific meaning and event type.

## Snapshot identity

Record:

- provider;
- model ID/alias;
- resolved model if available;
- date/time;
- endpoint;
- adapter version;
- profile;
- request settings;
- response IDs.

Aliases are not stable snapshots. The report must say so.
