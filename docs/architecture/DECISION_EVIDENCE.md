# Decision evidence

Each model step has two first-class CAS artifacts:

1. `zgw.observation/v1`, containing the exact observation, policy settings,
   state fingerprint and assistance declaration;
2. `zgw.decision-trace/v1`, containing calls, candidates, verdicts, selection
   rationale, final action and gateway statistics.

Each provider attempt points directly to its canonical request and normalized
response. When the adapter exposes the lowered wire payload, the attempt also
points to wire request, wire response and reasoning telemetry artifacts.

Large content stays in CAS. SQLite keeps identifiers, media types and indexed
relationships. Events remain an append-only audit trail, so a report can be
rebuilt without replacing original evidence with a summary.

Provider telemetry is not hidden chain-of-thought. A missing reasoning field is
stored as unavailable. A provider summary is stored as a provider summary.
Token counts never prove what the model privately considered.

The read-only command below exposes the chain for one step:

```text
zugzwang trace step STEP_ID
```

The output labels live decision evidence and post-hoc metrics separately.
