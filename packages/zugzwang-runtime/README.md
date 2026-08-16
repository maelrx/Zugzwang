# zugzwang-runtime

**Purpose:** Application services, durable local orchestration, state machines, repositories ports, budgets, persistence coordination and bundle assembly.

**First milestone:** `M1`

## Allowed dependencies

zugzwang-core plus persistence/application dependencies approved by ADR.

## Forbidden dependencies/behavior

Provider-specific semantics, concrete chess policy, UI logic, arbitrary plugin internals.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
