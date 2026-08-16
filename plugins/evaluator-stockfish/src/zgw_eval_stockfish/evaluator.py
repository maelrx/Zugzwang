"""Stockfish post-hoc evaluator plugin (ADR-024).

Post-hoc by default: the engine never enters the decision loop. The evaluator
consumes committed steps (position + action), analyzes each position through
the UCI boundary, and emits versioned metrics: legal rate, CPL/ACPL,
blunder/mistake/inaccuracy classification and best-move agreement. Engine
cache is keyed by binary/options/limit/MultiPV/state (ADR-026).
"""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.evaluator import (
    EvaluationContext,
    EvaluatorDescriptor,
    EvaluatorResult,
    MetricDefinition,
    MetricDirection,
    MetricObservation,
    MetricScope,
)

from .uci import EngineAnalysis, EngineLimit


@runtime_checkable
class UciEngineLike(Protocol):
    async def start(self) -> Any: ...

    async def position(self, fen: str, moves: list[str] | None = None) -> None: ...

    async def go(self, limit: EngineLimit, multipv: int = 1) -> EngineAnalysis: ...

    async def quit(self) -> None: ...


def cp_score(analysis: EngineAnalysis, side_to_move: str) -> float | None:
    """Normalize a score to centipawns from the mover's perspective."""
    for score in analysis.scores:
        if score.multipv != 1:
            continue
        if score.kind == "cp":
            value = float(score.value)
            return value if side_to_move == "white" else -value
        if score.kind == "mate":
            # mate in N for the side to move: sign convention (positive = good for mover)
            return 10000.0 - 100.0 * abs(score.value) if score.value > 0 else -10000.0
    return None


BLUNDER_THRESHOLD = 300.0
MISTAKE_THRESHOLD = 100.0
INACCURACY_THRESHOLD = 50.0


class StockfishEvaluator:
    evaluator_id = "evaluator.stockfish"
    evaluator_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        engine: UciEngineLike,
        *,
        limit: EngineLimit | None = None,
        multipv: int = 1,
        binary_metadata: dict[str, JsonValue] | None = None,
        use_cache: bool = True,
    ) -> None:
        self._engine = engine
        self._limit = limit or {"nodes": 100000}
        self._multipv = multipv
        self._binary_metadata = binary_metadata or {}
        self._use_cache = use_cache
        self._cache: dict[str, EngineAnalysis] = {}
        self._cache_hits = 0

    @property
    def descriptor(self) -> EvaluatorDescriptor:
        return EvaluatorDescriptor(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            plugin_api=self.plugin_api,
            metric_definitions=(
                MetricDefinition(
                    metric_id="chess.cpl",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="centipawn",
                    direction=MetricDirection.LOWER,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.move_class",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="category",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.best_move_agreement",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="boolean",
                    direction=MetricDirection.HIGHER,
                    provenance_source="engine",
                ),
            ),
            requires_engine=True,
        )

    async def evaluate(self, context: EvaluationContext) -> EvaluatorResult:
        """Evaluate the steps referenced in the evaluation context."""
        await self._engine.start()
        try:
            steps = context.evaluator_config.get("steps")
            observations: list[MetricObservation] = []
            if not isinstance(steps, list):
                return EvaluatorResult(observations=())
            previous_score: float | None = None
            for step_raw in steps:
                if not isinstance(step_raw, dict):
                    continue
                step = step_raw
                fen = step.get("fen")
                action = step.get("action")
                side = str(step.get("side_to_move", "white"))
                if not isinstance(fen, str) or not isinstance(action, str):
                    continue
                analysis = await self._analyze(fen, step.get("moves") or [], side)
                score = cp_score(analysis, side)
                cpl = (
                    max(previous_score - score, 0.0)
                    if previous_score is not None and score is not None
                    else None
                )
                move_class = classify_move(cpl) if cpl is not None else "none"
                best_agreement = analysis.bestmove == action
                step_id = str(step.get("step_id") or "")
                if cpl is not None:
                    observations.append(
                        MetricObservation(
                            metric_id="chess.cpl",
                            metric_version="1.0.0",
                            value_num=round(cpl, 2),
                            unit="centipawn",
                            dimensions={"phase": phase_of(step.get("fullmove_number"))},
                            run_id=context.run_id,
                            episode_id=context.episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                            observed_at=utc_now(),
                        )
                    )
                observations.append(
                    MetricObservation(
                        metric_id="chess.move_class",
                        metric_version="1.0.0",
                        value_text=str(move_class),
                        unit="category",
                        dimensions={},
                        run_id=context.run_id,
                        episode_id=context.episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                        observed_at=utc_now(),
                    )
                )
                observations.append(
                    MetricObservation(
                        metric_id="chess.best_move_agreement",
                        metric_version="1.0.0",
                        value_num=1.0 if best_agreement else 0.0,
                        unit="boolean",
                        dimensions={},
                        run_id=context.run_id,
                        episode_id=context.episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                        observed_at=utc_now(),
                    )
                )
                previous_score = score
            return EvaluatorResult(
                observations=tuple(observations),
                plugin_events=(
                    {
                        "evaluator": self.evaluator_id,
                        "cache_hits": self._cache_hits,
                        "limit": {str(k): int(v) for k, v in self._limit.items()},
                        "binary": self._binary_metadata,
                    },
                ),
            )
        finally:
            await self._engine.quit()

    async def _analyze(self, fen: str, moves: Any, side: str) -> EngineAnalysis:
        moves_list = [str(m) for m in cast(list[Any], moves)] if isinstance(moves, list) else []
        key = (
            f"{self._binary_metadata.get('binary_sha256', 'unknown')}|"
            f"{sorted(self._limit.items())}|{self._multipv}|{fen}|{moves_list}"
        )
        if self._use_cache and key in self._cache:
            self._cache_hits += 1
            return self._cache[key]
        await self._engine.position(fen, moves_list)
        analysis = await self._engine.go(self._limit, self._multipv)
        if self._use_cache:
            self._cache[key] = analysis
        return analysis


def classify_move(cpl: float) -> str:
    if cpl >= BLUNDER_THRESHOLD:
        return "blunder"
    if cpl >= MISTAKE_THRESHOLD:
        return "mistake"
    if cpl >= INACCURACY_THRESHOLD:
        return "inaccuracy"
    return "best_or_good"


def phase_of(fullmove_number: Any) -> str:
    try:
        number = int(fullmove_number)
    except (TypeError, ValueError):
        return "unknown"
    if number <= 10:
        return "opening"
    if number <= 30:
        return "middlegame"
    return "endgame"


class StockfishEvaluatorDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="evaluator.stockfish",
            plugin_version="0.1.0",
            kind=PluginKind.EVALUATOR,
            capabilities=("chess.cp_eval", "chess.multipv", "chess.mate"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


plugin_definition = StockfishEvaluatorDefinition()
