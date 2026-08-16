# zugzwang-core

**Purpose:** Pure domain model and public contracts: IDs, manifests, events, ports, budgets, assistance, metrics and errors.

**First milestone:** `M0`

## Allowed dependencies

Python stdlib and deliberately accepted lightweight type/schema dependencies at boundaries.

## Forbidden dependencies/behavior

Typer, FastAPI, SQLAlchemy, provider SDKs, concrete chess libraries, filesystem/network implementations, Stockfish.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
