# Arquitetura de avaliação

## Evaluator contract

```python
class Evaluator(Protocol):
    descriptor: EvaluatorDescriptor

    async def evaluate(
        self,
        subject: EvaluationSubject,
        context: EvaluationContext,
    ) -> MetricBundle: ...
```

## Live versus post-hoc

- live verifier can affect action and assistance;
- post-hoc evaluator cannot change trajectory;
- same engine may play both roles, but they are different plugins/configurations/events.

## Metric identity

```text
metric_id
metric_version
evaluator_id
evaluator_version
config_hash
subject_hash
```

Metrics append. They do not overwrite.

## Initial metrics

### Protocol

- parse success;
- legal first attempt;
- final legal;
- attempts;
- timeouts;
- violations.

### State

- exact state;
- piece-square F1;
- metadata field accuracy;
- affordance distance.

### Decision

- engine rank;
- clipped CP loss;
- WDL loss;
- top-k;
- blunder thresholds;
- calibration.

### System

- calls;
- input/output tokens;
- latency;
- estimated/actual cost;
- throughput.

### Explanation

- atomic claim correctness;
- completeness;
- action-reasoning consistency;
- counterfactual response.

## Engine configuration

Stockfish post-hoc config is immutable per evaluation run. Record binary and NNUE hashes, threads, hash size, depth/time/nodes, MultiPV and mate normalization.

## Statistical reports

Reporters consume metric tables. They do not write domain truth. Statistical code and report templates receive version IDs and artifact hashes.

## Re-evaluation

A bundle can acquire new metric observations under a new evaluation namespace without mutating original events.
