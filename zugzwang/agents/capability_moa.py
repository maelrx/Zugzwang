from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from zugzwang.providers.base import ProviderResponse
from zugzwang.strategy.validator import validate_move_response


@dataclass(frozen=True)
class AgentTrace:
    role: str
    raw_response: str
    move_uci: str | None
    parse_ok: bool
    is_legal: bool
    error: str | None
    tokens_input: int
    tokens_output: int
    latency_ms: int
    cost_usd: float
    provider_model: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityMoaResult:
    move_uci: str | None
    raw_response: str
    parse_ok: bool
    is_legal: bool
    error: str | None
    provider_model: str
    provider_calls: int
    tokens_input: int
    tokens_output: int
    latency_ms: int
    cost_usd: float
    traces: list[AgentTrace]
    aggregator_rationale: str | None = None


class CapabilityMoaOrchestrator:
    """Simple capability-MoA baseline: proposer set + single aggregator."""

    def __init__(
        self,
        *,
        call_provider: Callable[[list[dict[str, str]]], ProviderResponse],
        model: str,
    ) -> None:
        self._call_provider = call_provider
        self._default_model = model

    def decide(
        self,
        *,
        base_prompt: str,
        legal_moves_uci: list[str],
        proposer_roles: list[str],
        include_legal_moves_in_aggregator: bool = True,
    ) -> CapabilityMoaResult:
        traces: list[AgentTrace] = []
        candidates: list[str] = []

        totals = {
            "provider_calls": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "latency_ms": 0,
            "cost_usd": 0.0,
        }
        last_raw_response = ""
        last_model = self._default_model

        for role in proposer_roles:
            response = self._call_provider(
                [{"role": "user", "content": _build_proposer_prompt(base_prompt, role)}]
            )
            totals["provider_calls"] += 1
            totals["tokens_input"] += response.input_tokens
            totals["tokens_output"] += response.output_tokens
            totals["latency_ms"] += response.latency_ms
            totals["cost_usd"] += response.cost_usd
            last_raw_response = response.text
            last_model = response.model

            validation = validate_move_response(response.text, legal_moves_uci)
            trace = AgentTrace(
                role=role,
                raw_response=response.text,
                move_uci=validation.move_uci,
                parse_ok=validation.parse_ok,
                is_legal=validation.is_legal,
                error=validation.error_code,
                tokens_input=response.input_tokens,
                tokens_output=response.output_tokens,
                latency_ms=response.latency_ms,
                cost_usd=response.cost_usd,
                provider_model=response.model,
            )
            traces.append(trace)
            if validation.parse_ok and validation.is_legal and validation.move_uci:
                candidates.append(validation.move_uci)

        aggregator_prompt = _build_aggregator_prompt(
            base_prompt=base_prompt,
            traces=traces,
            legal_moves_uci=legal_moves_uci,
            include_legal_moves=include_legal_moves_in_aggregator,
        )
        response = self._call_provider([{"role": "user", "content": aggregator_prompt}])
        totals["provider_calls"] += 1
        totals["tokens_input"] += response.input_tokens
        totals["tokens_output"] += response.output_tokens
        totals["latency_ms"] += response.latency_ms
        totals["cost_usd"] += response.cost_usd
        last_raw_response = response.text
        last_model = response.model

        validation = validate_move_response(response.text, legal_moves_uci)
        traces.append(
            AgentTrace(
                role="aggregator",
                raw_response=response.text,
                move_uci=validation.move_uci,
                parse_ok=validation.parse_ok,
                is_legal=validation.is_legal,
                error=validation.error_code,
                tokens_input=response.input_tokens,
                tokens_output=response.output_tokens,
                latency_ms=response.latency_ms,
                cost_usd=response.cost_usd,
                provider_model=response.model,
            )
        )

        if validation.parse_ok and validation.is_legal and validation.move_uci:
            rationale = _build_aggregator_rationale(
                selected_move=validation.move_uci,
                proposer_candidates=candidates,
                aggregator_valid=True,
                used_fallback=False,
                error=None,
            )
            return CapabilityMoaResult(
                move_uci=validation.move_uci,
                raw_response=response.text,
                parse_ok=True,
                is_legal=True,
                error=None,
                provider_model=response.model,
                provider_calls=int(totals["provider_calls"]),
                tokens_input=int(totals["tokens_input"]),
                tokens_output=int(totals["tokens_output"]),
                latency_ms=int(totals["latency_ms"]),
                cost_usd=float(totals["cost_usd"]),
                traces=traces,
                aggregator_rationale=rationale,
            )

        voted = _majority_vote(candidates)
        if voted:
            rationale = _build_aggregator_rationale(
                selected_move=voted,
                proposer_candidates=candidates,
                aggregator_valid=False,
                used_fallback=True,
                error=validation.error_code or "invalid_aggregator_output",
            )
            return CapabilityMoaResult(
                move_uci=voted,
                raw_response=last_raw_response,
                parse_ok=True,
                is_legal=True,
                error="moa_aggregator_invalid_fallback_candidate",
                provider_model=last_model,
                provider_calls=int(totals["provider_calls"]),
                tokens_input=int(totals["tokens_input"]),
                tokens_output=int(totals["tokens_output"]),
                latency_ms=int(totals["latency_ms"]),
                cost_usd=float(totals["cost_usd"]),
                traces=traces,
                aggregator_rationale=rationale,
            )

        rationale = _build_aggregator_rationale(
            selected_move=None,
            proposer_candidates=candidates,
            aggregator_valid=False,
            used_fallback=False,
            error=validation.error_code or "moa_no_legal_candidate",
        )
        return CapabilityMoaResult(
            move_uci=None,
            raw_response=last_raw_response,
            parse_ok=False,
            is_legal=False,
            error=validation.error_code or "moa_no_legal_candidate",
            provider_model=last_model,
            provider_calls=int(totals["provider_calls"]),
            tokens_input=int(totals["tokens_input"]),
            tokens_output=int(totals["tokens_output"]),
            latency_ms=int(totals["latency_ms"]),
            cost_usd=float(totals["cost_usd"]),
            traces=traces,
            aggregator_rationale=rationale,
        )


def _build_proposer_prompt(base_prompt: str, role: str) -> str:
    capability_notes = {
        "reasoning": "Prioritize concrete tactical calculation.",
        "compliance": "Prioritize strict instruction following and legal move compliance.",
        "safety": "Prioritize king safety and blunder avoidance.",
    }
    note = capability_notes.get(role, "Prioritize robust chess decision quality.")
    return "\n".join(
        [
            base_prompt,
            f"Capability role: {role}.",
            note,
            "Propose exactly one legal move in UCI format only.",
        ]
    )


def _build_aggregator_prompt(
    *,
    base_prompt: str,
    traces: list[AgentTrace],
    legal_moves_uci: list[str],
    include_legal_moves: bool,
) -> str:
    lines = [
        base_prompt,
        "You are the aggregator. Pick the final move from candidate proposals.",
        "Choose exactly one legal UCI move.",
        "Candidates:",
    ]
    for trace in traces:
        lines.append(f"- {trace.role}: {trace.raw_response}")
    if include_legal_moves:
        lines.append(f"Legal moves (UCI): {', '.join(legal_moves_uci)}")
    lines.append("Return exactly one legal UCI move and no extra text.")
    return "\n".join(lines)


def _majority_vote(candidates: list[str]) -> str | None:
    if not candidates:
        return None
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate] = counts.get(candidate, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _build_aggregator_rationale(
    *,
    selected_move: str | None,
    proposer_candidates: list[str],
    aggregator_valid: bool,
    used_fallback: bool,
    error: str | None,
) -> str:
    if not proposer_candidates and selected_move is None:
        return f"No legal proposer candidates and no valid aggregator move. error={error or 'unknown'}."

    vote_counts: dict[str, int] = {}
    for candidate in proposer_candidates:
        vote_counts[candidate] = vote_counts.get(candidate, 0) + 1

    selected_support = vote_counts.get(selected_move or "", 0)
    total_proposers = len(proposer_candidates)
    top_candidate = None
    if vote_counts:
        top_candidate = sorted(vote_counts.items(), key=lambda item: (-item[1], item[0]))[0]

    if aggregator_valid:
        mode_line = "Aggregator output accepted."
    elif used_fallback:
        mode_line = "Aggregator output invalid; proposer majority fallback used."
    else:
        mode_line = "Aggregator and proposer selection could not produce a legal move."

    selected_line = (
        f"Selected move={selected_move}, proposer_support={selected_support}/{total_proposers}."
        if selected_move is not None
        else "Selected move unavailable."
    )
    top_line = (
        f"Top proposer candidate={top_candidate[0]} with {top_candidate[1]}/{total_proposers} votes."
        if top_candidate is not None
        else "No proposer vote information available."
    )
    error_line = f"error={error}" if error else "error=none"
    return " ".join([mode_line, selected_line, top_line, error_line])
