"""Registry entries for the built-in fakes.

Built-ins follow the same descriptor shape as entry-point plugins so the
registry treats them uniformly (design §24.2).
"""

from __future__ import annotations

from .fake_backend import FakeBackendDefinition
from .fake_environment import FakeEnvironmentDefinition
from .fake_evaluator import FakeEvaluatorDefinition
from .fake_strategy import FakeStrategyDefinition

FAKE_BACKEND_ENTRY = FakeBackendDefinition()
FAKE_ENVIRONMENT_ENTRY = FakeEnvironmentDefinition()
FAKE_EVALUATOR_ENTRY = FakeEvaluatorDefinition()
FAKE_STRATEGY_ENTRY = FakeStrategyDefinition()


class FakeTaskDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="fake.counter",
            plugin_version="0.1.0",
            kind=PluginKind.TASK,
            capabilities=("episode_builder",),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class FakePolicyDefinition:
    """A passive policy that never acts (role placeholder for single-player tasks)."""

    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="fake.stay",
            plugin_version="0.1.0",
            kind=PluginKind.POLICY,
            capabilities=("passive",),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


FAKE_TASK_ENTRY = FakeTaskDefinition()
FAKE_POLICY_ENTRY = FakePolicyDefinition()
