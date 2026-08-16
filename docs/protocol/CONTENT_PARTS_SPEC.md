# Content parts specification

## Union

```json
{
  "kind": "text | structured_state | image_artifact | tool_result",
  "...": "kind-specific fields"
}
```

## Text

```json
{
  "kind": "text",
  "text": "...",
  "language": "en",
  "semantic_role": "instruction"
}
```

## Structured state

```json
{
  "kind": "structured_state",
  "schema_id": "chess-state-v1",
  "value": {},
  "authority": "canonical"
}
```

## Image artifact

```json
{
  "kind": "image_artifact",
  "artifact_ref": "sha256:...",
  "mime_type": "image/png",
  "width": 1024,
  "height": 1024,
  "source_state_hash": "sha256:...",
  "renderer": {
    "id": "zugzwang.board",
    "version": "0.1.0"
  },
  "authority": "redundant"
}
```

## Tool result

```json
{
  "kind": "tool_result",
  "tool_call_id": "...",
  "tool_id": "chess.legal_moves",
  "result_schema": "legal-moves-v1",
  "artifact_ref": "sha256:...",
  "assistance_impact_h": "H3",
  "knowledge_impact_k": "K0"
}
```

## Authority values

- canonical;
- redundant;
- advisory;
- intentionally_conflicting;
- unknown.

## Lowering

Backend may transform parts into provider-specific wire format. It emits a lowering report and artifact hash.
