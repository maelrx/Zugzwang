# zugzwang-chess

**Purpose:** Standard-chess environment, codecs, renderers, tasks, opponents and rules-library adapter.

**First milestone:** `M2`

## Allowed dependencies

zugzwang-core environment contracts plus accepted rules/rendering substrate.

## Forbidden dependencies/behavior

Runtime DB access, provider SDKs, CLI commands, live strategic engine evaluation in environment.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
