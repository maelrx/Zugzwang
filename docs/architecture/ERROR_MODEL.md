# Error model

## Principles

- typed at boundaries;
- stable machine code;
- human message;
- retryability declared;
- ownership layer declared;
- raw cause retained internally;
- no provider exception types leak publicly.

## Categories

| Prefix | Category |
|---|---|
| `CFG` | configuration/manifest |
| `CAP` | unsupported capability |
| `PRV` | provider/transport |
| `OUT` | outcome unknown |
| `PAR` | parse |
| `ACT` | illegal/invalid action |
| `BUD` | budget |
| `TOL` | tool |
| `ENV` | environment |
| `PST` | persistence |
| `ART` | artifact |
| `EVAL` | evaluation |
| `PLG` | plugin |
| `PROT` | protocol violation |
| `SEC` | security |
| `COMP` | compatibility |

## Example

```json
{
  "code": "CAP-001",
  "message": "Required capability image_input is unavailable.",
  "retryable": false,
  "layer": "provider_resolution",
  "context": {
    "provider": "local-openai-compatible",
    "model": "..."
  }
}
```

## Exit codes

CLI maps categories to stable exit codes documented in protocol/ERROR_CODES.md.
