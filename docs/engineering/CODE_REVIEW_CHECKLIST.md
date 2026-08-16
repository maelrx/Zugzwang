# Checklist de code review

## Correctness

- [ ] Requirement and acceptance criteria are explicit.
- [ ] Error and cancellation paths are covered.
- [ ] Time, money, IDs and unknown values retain semantics.
- [ ] No committed action can be applied twice.

## Architecture

- [ ] Dependency direction is legal.
- [ ] SDK/concrete library types stop at adapter boundary.
- [ ] CLI/API contains no domain or SQL logic.
- [ ] Plugin receives narrow ports, not internal sessions.

## Scientific integrity

- [ ] H/K assistance is propagated and audited.
- [ ] Retries, selection and fallback are explicit attempts.
- [ ] Metric provenance is complete.
- [ ] Comparison does not mix protocols or distributions silently.

## Data/security

- [ ] Artifact retention follows policy.
- [ ] No secret/raw response enters logs or Git unexpectedly.
- [ ] Migration/upcaster behavior is tested.
- [ ] External process/network calls are bounded and attributable.

## Maintainability

- [ ] Public API delta is intentional.
- [ ] Tests prove invariant, not implementation trivia.
- [ ] Docs/schema/examples changed together.
- [ ] Follow-ups are issues, not vague TODOs.
