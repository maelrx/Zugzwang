"""ZGW-0075: reason-first/constrain-later (G4), SAN grounding (G3) and
protocol-level prompt overrides (persona + few-shot)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_DIR = REPO_ROOT / "experiments" / "research-suite-0.1"


@pytest.mark.integration
class TestReasonThenGround:
    @pytest.fixture
    def workspace(self, tmp_path) -> Workspace:
        ws = Workspace.from_root(tmp_path / "ws")
        ws.ensure_layout()
        return ws

    @pytest.mark.asyncio
    async def test_g4_two_phases_commit_legal_move(self, workspace: Workspace) -> None:
        from zugzwang_runtime.application.commands import StartRunCommand

        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(
            StartRunCommand(manifest_path=SUITE_DIR / "ground-001-g4.yaml"), asyncio.Event()
        )
        assert result.status == "COMPLETED", result
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        committed = connection.execute(
            "SELECT action_json FROM steps WHERE status='COMMITTED'"
        ).fetchall()
        assert len(committed) == 1
        assert committed[0][0] == '{"action": "e2e4"}'
        attempts = connection.execute(
            "SELECT COUNT(*) FROM attempts WHERE kind='provider' AND status='completed'"
        ).fetchone()
        assert attempts[0] == 2, "G4 must make exactly two calls (analyze + ground)"
        effective = connection.execute("SELECT effective_assistance FROM episodes").fetchone()
        assert effective[0] == "H3/K0", "legal grounding must raise effective H to H3"

    @pytest.mark.asyncio
    async def test_g4_prompt_override_recorded_in_request(self, workspace: Workspace) -> None:
        from zugzwang_runtime.application.commands import StartRunCommand

        services = DurableRunServices(workspace, PluginRegistry())
        await services.start(
            StartRunCommand(manifest_path=SUITE_DIR / "ground-001-g4.yaml"), asyncio.Event()
        )
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        request_artifacts = connection.execute(
            "SELECT relative_path FROM artifacts "
            "WHERE media_type='application/vnd.zugzwang.model-request+json'"
        ).fetchall()
        assert len(request_artifacts) == 2
        import json

        for (relative_path,) in request_artifacts:
            payload = json.loads(
                (workspace.objects_dir() / relative_path).read_text(encoding="utf-8")
            )
            joined = json.dumps(payload)
            assert "Grandmaster" in joined, "persona override must reach the request"

    @pytest.mark.asyncio
    async def test_g4_phase1_hides_legal_set(self, workspace: Workspace) -> None:
        from zugzwang_runtime.application.commands import StartRunCommand

        services = DurableRunServices(workspace, PluginRegistry())
        await services.start(
            StartRunCommand(manifest_path=SUITE_DIR / "ground-001-g4.yaml"), asyncio.Event()
        )
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        request_artifacts = connection.execute(
            "SELECT relative_path FROM artifacts "
            "WHERE media_type='application/vnd.zugzwang.model-request+json'"
        ).fetchall()
        import json

        phase1, phase2 = None, None
        for (relative_path,) in request_artifacts:
            payload = json.loads(
                (workspace.objects_dir() / relative_path).read_text(encoding="utf-8")
            )
            phase = payload.get("extensions", {}).get("chess.phase")
            if phase == "analyze":
                phase1 = json.dumps(payload)
            if phase == "ground":
                phase2 = json.dumps(payload)
        assert phase1 is not None and phase2 is not None
        assert "Legal moves" not in phase1, "phase 1 must not expose the legal set"
        assert "Legal moves" in phase2, "phase 2 must expose the legal set"


@pytest.mark.unit
class TestPromptHooks:
    def test_program_override_applies_persona_and_examples(self) -> None:
        from zugzwang_chess.strategies._prompt_hooks import apply_prompt_override
        from zugzwang_core.domain.prompt_program import PromptProgram
        from zugzwang_core.ports.model import ModelRef
        from zugzwang_core.ports.strategy import DecisionContext

        program = PromptProgram(
            template_id="tmpl.test", version="1.0.0", system_instructions="base"
        )
        context = DecisionContext(
            run_id="r",
            episode_id="e",
            step_id="s",
            model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
            backend=None,  # type: ignore[arg-type]
            tools={},
            seed=1,
            config={
                "prompt": {
                    "system_instructions": "You are a Grandmaster.",
                    "examples": [{"label": "x", "text": "Example body"}],
                }
            },
        )
        overridden = apply_prompt_override(program, context)
        assert overridden.system_instructions == "You are a Grandmaster."
        assert overridden.examples == ({"label": "x", "text": "Example body"},)
        untouched = apply_prompt_override(program, context.model_copy(update={"config": {}}))
        assert untouched is program

    def test_text_override_for_grounded_style_prompts(self) -> None:
        from zugzwang_chess.strategies._prompt_hooks import apply_prompt_override_text
        from zugzwang_core.ports.model import ModelRef
        from zugzwang_core.ports.strategy import DecisionContext

        context = DecisionContext(
            run_id="r",
            episode_id="e",
            step_id="s",
            model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
            backend=None,  # type: ignore[arg-type]
            tools={},
            seed=1,
            config={
                "prompt": {
                    "system_instructions": "Persona line.",
                    "examples": [{"label": "a", "text": "demo text"}],
                }
            },
        )
        out = apply_prompt_override_text("The prompt.", context)
        assert out.startswith("Persona line.")
        assert "Example a:\ndemo text" in out


@pytest.mark.integration
class TestSanGrounding:
    @pytest.mark.asyncio
    async def test_grounded_san_legal_set_commits_uci(self, tmp_path) -> None:
        from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
        from zugzwang_chess.strategies.grounded import GroundedStrategy
        from zugzwang_core.ports.environment import ObservationPolicy
        from zugzwang_core.ports.model import ModelRef
        from zugzwang_core.ports.strategy import DecisionContext
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule

        env = StandardChessEnvironment()
        state = ChessGameState(fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        policy = ObservationPolicy(
            settings={
                "position": {"fen": True},
                "side_to_move": True,
                "legal_actions": {"exposure": "always", "encoding": "san"},
            }
        )
        observation = env.observe(state, policy)
        assert all(isinstance(a, str) and not a[0].isdigit() for a in observation["legal_actions"])
        backend = DeterministicModelBackend(
            rules=(FakeBackendRule(when={"fingerprint_contains": "chess-grounded"}, output="Nf3"),)
        )
        strategy = GroundedStrategy()
        context = DecisionContext(
            run_id="r",
            episode_id="e",
            step_id="s",
            model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
            backend=backend,
            tools={},
            seed=1,
        )
        trace = await strategy.decide(observation, context)
        assert trace.final_action == "g1f3", "SAN choice must resolve to canonical UCI"
        assert trace.termination_reason == "selected"
