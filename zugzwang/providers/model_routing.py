from __future__ import annotations


KIMI_K25_ALIASES = {
    "kimi-2.5",
    "kimi_2.5",
    "kimi-k2.5",
    "kimi_k2.5",
    "k2.5",
    "k2_5",
    "kimi-for-coding",
}


def resolve_provider_and_model(
    provider: str | None,
    model: str | None,
) -> tuple[str, str | None]:
    provider_id = (provider or "").strip().lower()
    model_id = model.strip() if isinstance(model, str) else None
    normalized_model = (model_id or "").strip().lower()

    if provider_id in {"kimi", "kimicode"} and normalized_model in KIMI_K25_ALIASES:
        return "kimicode", "kimi-for-coding"

    return provider_id, model_id
