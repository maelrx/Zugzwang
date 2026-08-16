# Provider contract

## Contract objective

Normalize one model inference while preserving provider-specific evidence.

## Request fields

```yaml
request_id:
model:
messages:
output_contract:
tools:
settings:
timeout:
capability_requirements:
metadata:
```

Messages contain typed content parts. Tool declarations are schemas only; strategy executes tools.

## Response fields

```yaml
request_id:
provider_request_id:
model_reported:
content_parts:
tool_calls:
finish_reason:
usage:
latency_ms:
raw_artifact_ref:
warnings:
outcome:
```

## Outcomes

- completed;
- provider_error;
- transport_error;
- throttled;
- timeout_before_send;
- outcome_unknown;
- canceled;
- capability_mismatch;
- policy_blocked.

## Capability negotiation

Backend must produce a `CapabilityReport` before plan execution. Capability may be:

- native;
- emulated;
- unsupported;
- unknown.

Emulation changes condition identity and must be enabled.

## Raw versus normalized

Canonical request, lowered provider request, normalized response and raw response are distinct artifacts. A retention policy may omit payloads, but cannot pretend they were retained.

## Usage

Record provider-reported and locally estimated values separately. Missing usage is `unknown`, not zero.

## Contract tests

Every adapter passes fixtures for:

- text;
- structured output;
- image input if declared;
- tool-call proposal if declared;
- timeout;
- malformed response;
- usage absence;
- unexpected message part;
- provider model alias;
- cancellation;
- retry classification.

## No hidden behavior

Adapters must not:

- auto-retry unless the kernel requests;
- fallback;
- route;
- execute tools;
- summarize history;
- mutate system prompts;
- add legal actions;
- coerce invalid structured output without event.
