# provider-openai-compatible

**Purpose:** Direct HTTP adapter for explicit OpenAI-compatible dialects and local inference servers.

**First milestone:** `M3`

## Allowed dependencies

Public provider contract and HTTP client.

## Forbidden dependencies/behavior

Assuming dialect equivalence, hidden model routing, silent field dropping.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.

## Wire profiles

The adapter defaults to openai-chat-completions. Set the explicit
openai-responses profile when the endpoint exposes /responses instead of
/chat/completions. The local ZCode/OpenCode loopback router at
http://127.0.0.1:8788/v1 exposes muse-spark-1.3-contributor-free through
this Responses profile; the router owns upstream authentication, so the
Zugzwang manifest should not contain a provider key.

Application metadata in ModelRequest.extensions is retained in canonical
evidence and is not sent as unknown provider fields. To intentionally pass a
wire extension, use the explicit provider.openai_compatible.<field> namespace.
