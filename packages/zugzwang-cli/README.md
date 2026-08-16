# zugzwang-cli

**Purpose:** Human and machine CLI adapter over application services.

**First milestone:** `M0-M1`

## Allowed dependencies

Application service public APIs, Typer after ADR ratification, presentation utilities.

## Forbidden dependencies/behavior

SQL, direct filesystem persistence, domain decisions, provider calls, chess rule logic.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
