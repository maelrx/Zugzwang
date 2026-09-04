# evaluator-stockfish

**Purpose:** External UCI Stockfish supervision and post-hoc versioned chess metrics.

**First milestone:** `M4`

The precise evaluator records CPL, move class, best-move agreement, the
engine's best UCI move and the score before and after each committed model
move. It uses the current FEN as the engine position and does not replay the
history a second time.

## Allowed dependencies

Public evaluator/tool contracts, process supervisor, chess canonical types.

## Forbidden dependencies/behavior

Bundled binary before gate, live advice in unassisted regime, unversioned eval defaults.

## Pre-scaffold status

This directory documents a physical boundary. Runtime/package metadata is created only by `bootstrap-workspace` after blocking gates are accepted.

## Public surface rule

Expose the narrowest contract needed by the next layer. Internal implementation modules are not plugin API by accident.

## Live opponent policy

The package also exposes the explicit chess.stockfish policy for a Stockfish
opponent that is separate from the model decision loop and from post-hoc
evaluation. Native UCI_Elo is recorded exactly. If a requested test bucket is
below the binary's native floor, `allow_approximate: true` enables the
weakest `Skill Level` profile and records that it is an approximation rather
than claiming a native Elo the engine does not support.

    policy:
      plugin: chess.stockfish
      config:
        executable: /path/to/stockfish
        elo: 1500
        limit: {nodes: 20000}
        options: {Threads: "1", Hash: "16"}

    # For a below-floor test bucket such as 1000 on Stockfish 16:
    #     elo: 1000
    #     allow_approximate: true

The opponent never receives model prompts and its moves are persisted with
engine path, binary hash, UCI options, requested/effective strength and limit
metadata.
