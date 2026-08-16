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
