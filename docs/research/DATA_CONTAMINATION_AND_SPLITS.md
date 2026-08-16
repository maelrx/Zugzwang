# Dados, contaminação e splits

## 1. Threat model

- public puzzles in pretraining;
- master games and openings widely mirrored;
- repeated positions and transpositions across splits;
- provider post-training after benchmark publication;
- bots/cheaters in human datasets;
- engine labels leaking through SAN `+/#`;
- retrieved examples containing continuations;
- image renderer encoding side information;
- same player or game crossing train/eval in future training work.

## 2. Split units

Depending on task:

- game;
- position family;
- player;
- opening;
- calendar time;
- source;
- motif;
- metamorphic group.

Position-level random split is often insufficient because adjacent plies and transpositions leak.

## 3. v0.1 data policy

The initial inference suite should:

- use public positions only when licensing allows redistribution;
- store source URL/id and transformation lineage;
- hash canonical state;
- deduplicate exact states;
- detect near transpositions where feasible;
- reserve a hidden holdout;
- include generated random-legal states;
- avoid current target retrieval;
- publish a data card.

## 4. Human data

Before claims about elite behavior:

- inspect BOT flags;
- exclude marked violations according to a documented rule;
- cluster by player;
- publish rating normalization;
- avoid treating platform ratings as FIDE equivalents.

## 5. Engine labels

Record:

- engine name/version/hash;
- NNUE file/hash;
- threads/hash;
- time/depth/nodes;
- MultiPV;
- adjudication;
- mate normalization.

Engine evaluation is a derived artifact and can be regenerated. Raw positions remain immutable.

## 6. Dataset card required fields

```yaml
dataset_id:
version:
license:
sources:
cutoff:
unit:
raw_count:
deduplicated_count:
split_strategy:
transposition_policy:
human_account_audit:
engine_labels:
known_contamination:
redistribution_constraints:
```

## 7. No silent correction

If source metadata is inconsistent, preserve raw input and add a normalized projection. Do not overwrite source evidence.
