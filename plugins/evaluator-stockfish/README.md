# evaluator-stockfish

**Purpose:** External UCI Stockfish supervision and post-hoc versioned chess metrics.

**First milestone:** `M4`

## Allowed dependencies

Public evaluator/tool contracts, process supervisor, chess canonical types.

## Forbidden dependencies/behavior

Bundled binary before gate, live advice in unassisted regime, unversioned eval defaults.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.
