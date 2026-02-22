from __future__ import annotations

import os
from dataclasses import dataclass


TOKENS_PER_MILLION = 1_000_000.0


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cached_input_per_mtok: float | None = None


# Source: https://docs.z.ai/guides/overview/pricing (accessed 2026-02-22)
ZAI_STANDARD_PRICING: dict[str, ModelPricing] = {
    "glm-5": ModelPricing(input_per_mtok=1.0, output_per_mtok=3.2, cached_input_per_mtok=0.2),
    "glm-5-code": ModelPricing(input_per_mtok=1.2, output_per_mtok=5.0, cached_input_per_mtok=0.3),
    "glm-4.7": ModelPricing(input_per_mtok=0.6, output_per_mtok=2.2, cached_input_per_mtok=0.11),
    "glm-4.7-flashx": ModelPricing(input_per_mtok=0.07, output_per_mtok=0.4, cached_input_per_mtok=0.01),
    "glm-4.6": ModelPricing(input_per_mtok=0.6, output_per_mtok=2.2, cached_input_per_mtok=0.11),
    "glm-4.5": ModelPricing(input_per_mtok=0.6, output_per_mtok=2.2, cached_input_per_mtok=0.11),
    "glm-4.5-x": ModelPricing(input_per_mtok=2.2, output_per_mtok=8.9, cached_input_per_mtok=0.45),
    "glm-4.5-air": ModelPricing(input_per_mtok=0.2, output_per_mtok=1.1, cached_input_per_mtok=0.03),
    "glm-4.5-airx": ModelPricing(input_per_mtok=1.1, output_per_mtok=4.5, cached_input_per_mtok=0.22),
    "glm-4-32b-0414-128k": ModelPricing(input_per_mtok=0.1, output_per_mtok=0.1, cached_input_per_mtok=None),
    "glm-4.7-flash": ModelPricing(input_per_mtok=0.0, output_per_mtok=0.0, cached_input_per_mtok=0.0),
    "glm-4.5-flash": ModelPricing(input_per_mtok=0.0, output_per_mtok=0.0, cached_input_per_mtok=0.0),
}


def normalize_model_name(model: str) -> str:
    return model.strip().lower()


def _custom_pricing_from_env() -> ModelPricing | None:
    input_rate = os.environ.get("ZAI_PRICE_INPUT_PER_MTOK")
    output_rate = os.environ.get("ZAI_PRICE_OUTPUT_PER_MTOK")
    cached_rate = os.environ.get("ZAI_PRICE_CACHED_INPUT_PER_MTOK")
    if input_rate is None or output_rate is None:
        return None
    return ModelPricing(
        input_per_mtok=float(input_rate),
        output_per_mtok=float(output_rate),
        cached_input_per_mtok=float(cached_rate) if cached_rate is not None else None,
    )


def pricing_mode_from_env() -> str:
    return os.environ.get("ZAI_PRICING_MODE", "standard").strip().lower()


def get_zai_pricing(model: str, mode: str | None = None) -> ModelPricing:
    pricing_mode = (mode or pricing_mode_from_env()).strip().lower()
    if pricing_mode == "custom":
        custom = _custom_pricing_from_env()
        if custom is not None:
            return custom
    normalized = normalize_model_name(model)
    if normalized in ZAI_STANDARD_PRICING:
        return ZAI_STANDARD_PRICING[normalized]
    # Safe fallback: unknown models default to zero-cost estimate to avoid false budget aborts.
    return ModelPricing(input_per_mtok=0.0, output_per_mtok=0.0, cached_input_per_mtok=0.0)


def estimate_zai_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_prompt_tokens: int = 0,
    mode: str | None = None,
) -> float:
    pricing_mode = (mode or pricing_mode_from_env()).strip().lower()
    if pricing_mode in {"coding_plan", "plan_included"}:
        return 0.0

    pricing = get_zai_pricing(model=model, mode=pricing_mode)
    uncached_input_tokens = max(0, int(prompt_tokens) - int(cached_prompt_tokens))
    cached_tokens = max(0, int(cached_prompt_tokens))
    output_tokens = max(0, int(completion_tokens))

    cached_rate = (
        pricing.cached_input_per_mtok
        if pricing.cached_input_per_mtok is not None
        else pricing.input_per_mtok
    )
    input_cost = (uncached_input_tokens / TOKENS_PER_MILLION) * pricing.input_per_mtok
    cached_cost = (cached_tokens / TOKENS_PER_MILLION) * cached_rate
    output_cost = (output_tokens / TOKENS_PER_MILLION) * pricing.output_per_mtok
    return float(input_cost + cached_cost + output_cost)
