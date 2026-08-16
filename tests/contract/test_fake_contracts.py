"""Contract tests: the fake implementations pass the shared contract suites."""

from __future__ import annotations

import pytest

from zugzwang_runtime.fakes import (
    CounterEnvironment,
    DeterministicModelBackend,
    FakeEvaluator,
)

from .contract_suite import (
    run_environment_contract,
    run_environment_invalid_action_contract,
    run_evaluator_contract,
    run_model_backend_contract,
)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_fake_backend_passes_model_contract() -> None:
    backend = DeterministicModelBackend(rules=())
    with pytest.raises(Exception, match="no fake rule matched"):
        await run_model_backend_contract(backend)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_fake_backend_contract_with_default_rule() -> None:
    from zugzwang_runtime.fakes import FakeBackendRule

    backend = DeterministicModelBackend(
        rules=(FakeBackendRule(when={"call_index": 0}, output="e2e4"),)
    )
    await run_model_backend_contract(backend)


@pytest.mark.contract
def test_fake_environment_passes_contract() -> None:
    run_environment_contract(CounterEnvironment())
    run_environment_invalid_action_contract(CounterEnvironment())


@pytest.mark.contract
@pytest.mark.asyncio
async def test_fake_evaluator_passes_contract() -> None:
    await run_evaluator_contract(FakeEvaluator())
