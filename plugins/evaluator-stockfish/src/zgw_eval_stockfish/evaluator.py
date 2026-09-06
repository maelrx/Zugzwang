"""Stockfish post-hoc evaluator plugin (ADR-024).

Post-hoc by default: the engine never enters the decision loop. The evaluator
consumes committed steps (position + action), analyzes each position through
the UCI boundary, and emits versioned metrics: legal rate, CPL/ACPL,
blunder/mistake/inaccuracy classification and best-move agreement. Engine
cache is keyed by binary/options/limit/MultiPV/state (ADR-026).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol, cast, runtime_checkable

import chess

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

from .uci import EngineAnalysis, EngineLimit, EngineLine, EngineScore


@runtime_checkable
class UciEngineLike(Protocol):
    async def start(self) -> Any: ...

    async def position(self, fen: str, moves: list[str] | None = None) -> None: ...

    async def go(self, limit: EngineLimit, multipv: int = 1) -> EngineAnalysis: ...

    async def quit(self) -> None: ...


def cp_score(analysis: EngineAnalysis, side_to_move: str) -> float | None:
    """Normalize a score to centipawns from the mover's perspective."""
    # UCI emits several ``info`` lines while it searches. The last score for
    # MultiPV 1 is the strongest available result in the transcript.
    for score in reversed(analysis.scores):
        if score.multipv != 1:
            continue
        if score.kind == "cp":
            value = float(score.value)
            # UCI reports the score from the root side-to-move perspective.
            # The caller already supplies that side, so do not negate Black.
            return value
        if score.kind == "mate":
            # mate in N for the side to move: sign convention (positive = good for mover)
            return 10000.0 - 100.0 * abs(score.value) if score.value > 0 else -10000.0
    return None


BLUNDER_THRESHOLD = 300.0
MISTAKE_THRESHOLD = 100.0
INACCURACY_THRESHOLD = 50.0


class StockfishEvaluator:
    evaluator_id = "evaluator.stockfish"
    evaluator_version = "0.3.0"
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
        self._analysis_records: list[dict[str, Any]] = []

    @property
    def analysis_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._analysis_records)

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
                MetricDefinition(
                    metric_id="chess.engine_best_move",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="uci",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.engine_score_before",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="centipawn",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.engine_score_after",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="centipawn",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.cp_before",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="centipawn",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.cp_after_chosen",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="centipawn",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.wdl_loss",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="probability",
                    direction=MetricDirection.LOWER,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.multipv_top_k",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="ranked_lines",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.chosen_rank",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="rank",
                    direction=MetricDirection.LOWER,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.mate_transition",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="category",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.principal_variation",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="uci_line",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.mate_before",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="plies_to_mate",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
                MetricDefinition(
                    metric_id="chess.mate_after",
                    version="1.0.0",
                    scope=MetricScope.STEP,
                    unit="plies_to_mate",
                    direction=MetricDirection.NONE,
                    provenance_source="engine",
                ),
            ),
            requires_engine=True,
        )

    @property
    def evaluation_metadata(self) -> dict[str, JsonValue]:
        """Immutable configuration recorded on every EvaluationRun."""
        return {
            "engine": "Stockfish",
            "binary": self._binary_metadata,
            "limit": {str(key): int(value) for key, value in self._limit.items()},
            "multipv": self._multipv,
            "evaluator_version": self.evaluator_version,
        }

    async def evaluate(self, context: EvaluationContext) -> EvaluatorResult:
        """Evaluate the steps referenced in the evaluation context."""
        await self._engine.start()
        try:
            steps = context.evaluator_config.get("steps")
            observations: list[MetricObservation] = []
            if not isinstance(steps, list):
                return EvaluatorResult(observations=())
            for step_raw in steps:
                if not isinstance(step_raw, dict):
                    continue
                step = step_raw
                fen = step.get("fen")
                action = step.get("action")
                side = str(step.get("side_to_move", "white"))
                if not isinstance(fen, str) or not isinstance(action, str):
                    continue
                analysis = await self._analyze(fen, [], side)
                before_score = _latest_score(analysis, 1)
                score_before = _cp_score_only(before_score)
                score_after: float | None = None
                after_score: EngineScore | None = None
                after_analysis: EngineAnalysis | None = None
                try:
                    board = chess.Board(fen)
                    move = chess.Move.from_uci(action)
                    if board.is_legal(move):
                        board.push(move)
                        after_side = "black" if side == "white" else "white"
                        after_analysis = await self._analyze(board.fen(), [], after_side)
                        after_score = _latest_score(after_analysis, 1)
                        after_score_from_next_mover = _cp_score_only(after_score)
                        if after_score_from_next_mover is not None:
                            score_after = -after_score_from_next_mover
                except (ValueError, chess.InvalidMoveError):
                    score_after = None
                episode_id = str(step.get("episode_id") or context.episode_id or "") or None
                cpl = _cpl(before_score, after_score, score_after)
                move_class = classify_move(cpl) if cpl is not None else "none"
                best_agreement = analysis.bestmove == action
                step_id = str(step.get("step_id") or "")
                best_line = _line_for(analysis, 1)
                chosen_rank = _chosen_rank(analysis, action)
                top_lines = _top_lines(analysis, self._multipv)
                wdl_loss = _wdl_loss(before_score, after_score)
                mate_transition = _mate_transition(before_score, after_score)
                if cpl is not None:
                    observations.append(
                        MetricObservation(
                            metric_id="chess.cpl",
                            metric_version="1.0.0",
                            value_num=round(cpl, 2),
                            unit="centipawn",
                            dimensions={"phase": phase_of(step.get("fullmove_number"))},
                            run_id=context.run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                            observed_at=utc_now(),
                        )
                    )
                if analysis.bestmove:
                    observations.append(
                        MetricObservation(
                            metric_id="chess.engine_best_move",
                            metric_version="1.0.0",
                            value_text=analysis.bestmove,
                            unit="uci",
                            dimensions={},
                            run_id=context.run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                            observed_at=utc_now(),
                        )
                    )
                if score_before is not None:
                    observations.append(
                        MetricObservation(
                            metric_id="chess.engine_score_before",
                            metric_version="1.0.0",
                            value_num=round(score_before, 2),
                            unit="centipawn",
                            dimensions={},
                            run_id=context.run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                            observed_at=utc_now(),
                        )
                    )
                if score_after is not None:
                    observations.append(
                        MetricObservation(
                            metric_id="chess.engine_score_after",
                            metric_version="1.0.0",
                            value_num=round(score_after, 2),
                            unit="centipawn",
                            dimensions={},
                            run_id=context.run_id,
                            episode_id=episode_id,
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
                        episode_id=episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                        observed_at=utc_now(),
                    )
                )
                for metric_id, value_num in (
                    ("chess.cp_before", score_before),
                    ("chess.cp_after_chosen", score_after),
                ):
                    if value_num is not None:
                        observations.append(
                            _step_metric(
                                metric_id=metric_id,
                                value_num=round(value_num, 2),
                                unit="centipawn",
                                context=context,
                                episode_id=episode_id,
                                step_id=step_id,
                                evaluator_id=self.evaluator_id,
                                evaluator_version=self.evaluator_version,
                            )
                        )
                if wdl_loss is not None:
                    observations.append(
                        _step_metric(
                            metric_id="chess.wdl_loss",
                            value_num=round(wdl_loss, 6),
                            unit="probability",
                            context=context,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                        )
                    )
                if chosen_rank is not None:
                    observations.append(
                        _step_metric(
                            metric_id="chess.chosen_rank",
                            value_num=float(chosen_rank),
                            unit="rank",
                            context=context,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                        )
                    )
                observations.append(
                    _step_metric(
                        metric_id="chess.multipv_top_k",
                        value_json=cast(dict[str, JsonValue], {"lines": top_lines}),
                        unit="ranked_lines",
                        context=context,
                        episode_id=episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                    )
                )
                observations.append(
                    _step_metric(
                        metric_id="chess.mate_transition",
                        value_text=mate_transition,
                        unit="category",
                        context=context,
                        episode_id=episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                    )
                )
                if best_line is not None and best_line.pv:
                    observations.append(
                        _step_metric(
                            metric_id="chess.principal_variation",
                            value_text=" ".join(best_line.pv),
                            unit="uci_line",
                            context=context,
                            episode_id=episode_id,
                            step_id=step_id,
                            evaluator_id=self.evaluator_id,
                            evaluator_version=self.evaluator_version,
                        )
                    )
                for mate_metric, score in (
                    ("chess.mate_before", before_score),
                    ("chess.mate_after", after_score),
                ):
                    if score is not None and score.kind == "mate":
                        observations.append(
                            _step_metric(
                                metric_id=mate_metric,
                                value_num=float(score.value),
                                unit="plies_to_mate",
                                context=context,
                                episode_id=episode_id,
                                step_id=step_id,
                                evaluator_id=self.evaluator_id,
                                evaluator_version=self.evaluator_version,
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
                        episode_id=episode_id,
                        step_id=step_id,
                        evaluator_id=self.evaluator_id,
                        evaluator_version=self.evaluator_version,
                        observed_at=utc_now(),
                    )
                )
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
        # FEN already describes the complete current position. Replaying the
        # full game after it would ask UCI to apply moves twice and can produce
        # invalid or silently ignored history.
        key = (
            f"{self._binary_metadata.get('binary_sha256', 'unknown')}|"
            f"{sorted(self._limit.items())}|{self._multipv}|{fen}"
        )
        if self._use_cache and key in self._cache:
            self._cache_hits += 1
            return self._cache[key]
        await self._engine.position(fen)
        analysis = await self._engine.go(self._limit, self._multipv)
        self._analysis_records.append(
            {
                "fen": fen,
                "side_to_move": side,
                "limit": dict(self._limit),
                "multipv": self._multipv,
                "analysis": asdict(analysis),
            }
        )
        if self._use_cache:
            self._cache[key] = analysis
        return analysis


def _latest_score(analysis: EngineAnalysis, multipv: int) -> EngineScore | None:
    for score in reversed(analysis.scores):
        if score.multipv == multipv:
            return score
    return None


def _cp_score_only(score: EngineScore | None) -> float | None:
    if score is None or score.kind != "cp":
        return None
    return float(score.value)


def _cpl(
    before: EngineScore | None,
    after: EngineScore | None,
    after_from_mover: float | None,
) -> float | None:
    # Mate is represented by explicit mate metrics. It is not converted into
    # an arbitrary centipawn infinity, so CPL remains a cp-to-cp quantity.
    if before is None or after is None or before.kind != "cp" or after.kind != "cp":
        return None
    before_value = float(before.value)
    if after_from_mover is None:
        return None
    return max(before_value - after_from_mover, 0.0)


def _line_for(analysis: EngineAnalysis, multipv: int) -> EngineLine | None:
    for line in analysis.lines:
        if line.score.multipv == multipv:
            if (
                multipv == 1
                and analysis.bestmove
                and (not line.pv or line.pv[0] != analysis.bestmove)
            ):
                return EngineLine(
                    score=line.score,
                    pv=(analysis.bestmove, *line.pv[1:]),
                )
            return line
    return None


def _chosen_rank(analysis: EngineAnalysis, action: str) -> int | None:
    if analysis.bestmove == action:
        return 1
    for line in analysis.lines:
        if line.pv and line.pv[0] == action:
            return line.score.multipv
    return None


def _top_lines(analysis: EngineAnalysis, limit: int) -> list[dict[str, JsonValue]]:
    lines: list[dict[str, JsonValue]] = []
    for line in sorted(analysis.lines, key=lambda item: item.score.multipv)[:limit]:
        pv = line.pv
        if line.score.multipv == 1 and analysis.bestmove:
            pv = (analysis.bestmove, *line.pv[1:]) if line.pv else (analysis.bestmove,)
        lines.append(
            {
                "rank": line.score.multipv,
                "move": pv[0] if pv else None,
                "score_kind": line.score.kind,
                "score": line.score.value,
                "pv": list(pv),
            }
        )
    if not lines and analysis.bestmove:
        score = _latest_score(analysis, 1)
        lines.append(
            {
                "rank": 1,
                "move": analysis.bestmove,
                "score_kind": score.kind if score else None,
                "score": score.value if score else None,
                "pv": [],
            }
        )
    return lines


def _wdl_loss(before: EngineScore | None, after: EngineScore | None) -> float | None:
    if before is None or after is None or before.wdl is None or after.wdl is None:
        return None
    before_total = sum(before.wdl)
    after_total = sum(after.wdl)
    if before_total <= 0 or after_total <= 0:
        return None
    before_win = before.wdl[0] / before_total
    # ``after`` is scored from the opponent's side-to-move perspective.
    after_win_for_mover = after.wdl[2] / after_total
    return max(before_win - after_win_for_mover, 0.0)


def _mate_transition(before: EngineScore | None, after: EngineScore | None) -> str:
    before_mate = before is not None and before.kind == "mate"
    after_mate = after is not None and after.kind == "mate"
    if before_mate and after_mate:
        return "mate_to_mate"
    if before_mate:
        return "mate_before"
    if after_mate:
        return "mate_after"
    return "none"


def _step_metric(
    *,
    metric_id: str,
    context: EvaluationContext,
    episode_id: str | None,
    step_id: str,
    unit: str,
    evaluator_id: str,
    evaluator_version: str,
    value_num: float | None = None,
    value_text: str | None = None,
    value_json: dict[str, JsonValue] | None = None,
) -> MetricObservation:
    return MetricObservation(
        metric_id=metric_id,
        metric_version="1.0.0",
        value_num=value_num,
        value_text=value_text,
        value_json=value_json,
        unit=unit,
        dimensions={},
        run_id=context.run_id,
        episode_id=episode_id,
        step_id=step_id,
        evaluator_id=evaluator_id,
        evaluator_version=evaluator_version,
        observed_at=utc_now(),
    )


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
