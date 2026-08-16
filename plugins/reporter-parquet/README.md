# reporter-parquet

**Purpose:** Analytical Parquet exports and reference DuckDB queries from stable projections.

**First milestone:** `M4`

## Allowed dependencies

Public report/metric contracts, Arrow/Parquet/DuckDB dependencies.

## Forbidden dependencies/behavior

Mutating operational DB/evidence, defining canonical runtime semantics.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
