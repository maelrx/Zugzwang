# Error codes

| Code | Meaning | Retry |
|---|---|---|
| `CFG-001` | source manifest invalid | no |
| `CFG-002` | cross-field invariant | no |
| `CFG-003` | unresolved human gate | no |
| `CAP-001` | required capability unavailable | no |
| `CAP-002` | emulation not authorized | no |
| `PRV-001` | provider transport failure | policy |
| `PRV-002` | provider error | policy |
| `PRV-003` | throttled | policy |
| `OUT-001` | call outcome unknown | manual/policy |
| `PAR-001` | response parse failed | R2 policy |
| `ACT-001` | illegal action | R2 policy |
| `BUD-001` | hard budget exceeded | no |
| `TOL-001` | tool input invalid | no |
| `ENV-001` | transition invariant failure | no |
| `PST-001` | database write failed | policy |
| `ART-001` | artifact integrity failure | no |
| `EVAL-001` | evaluator failed | post-hoc retry |
| `PLG-001` | plugin incompatible | no |
| `PROT-001` | effective assistance exceeds declaration | no |
| `SEC-001` | security policy blocked operation | no |
| `COMP-001` | unsupported schema major | no |

Errors may add context, never change code meaning within a major contract version.
