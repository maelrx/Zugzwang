# provider-pydantic-ai

**Purpose:** ModelBackend adapter using Pydantic AI Direct requests as low-level transport/schema substrate.

**First milestone:** `M3`

## Allowed dependencies

Public provider contract and pinned Pydantic AI integration APIs.

## Forbidden dependencies/behavior

Pydantic AI Agent semantics, hidden retries/tools/memory/fallback.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
