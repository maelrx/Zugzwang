from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from zugzwang.experiments.config_schema import validate_config
from zugzwang.strategy.prompts import DEFAULT_PROMPT_ID, resolve_system_prompt


DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "configs" / "defaults.yaml"


class ConfigError(ValueError):
    """Raised for config loading and merge failures."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise ConfigError(f"Config file not found: {path_obj}")
    raw = yaml.safe_load(path_obj.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"YAML root must be a mapping: {path_obj}")
    return raw


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def parse_override_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered == "null":
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def set_by_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = target
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value


def apply_cli_overrides(config: dict[str, Any], overrides: list[str] | None) -> dict[str, Any]:
    if not overrides:
        return config

    merged = copy.deepcopy(config)
    for item in overrides:
        if "=" not in item:
            raise ConfigError(f"Invalid override '{item}'. Expected dotted.path=value")
        key, raw_value = item.split("=", 1)
        set_by_path(merged, key.strip(), parse_override_value(raw_value.strip()))
    return merged


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def config_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def resolve_config(
    experiment_config_path: str | Path,
    model_profile_path: str | Path | None = None,
    cli_overrides: list[str] | None = None,
    defaults_path: str | Path | None = None,
) -> dict[str, Any]:
    defaults = load_yaml(defaults_path or DEFAULTS_PATH)
    resolved = defaults

    if model_profile_path:
        model_profile = load_yaml(model_profile_path)
        resolved = deep_merge(resolved, model_profile)

    experiment = load_yaml(experiment_config_path)
    resolved = deep_merge(resolved, experiment)
    resolved = apply_cli_overrides(resolved, cli_overrides)

    validate_config(resolved)
    _inject_prompt_resolution_metadata(resolved)
    return resolved


def resolve_with_hash(
    experiment_config_path: str | Path,
    model_profile_path: str | Path | None = None,
    cli_overrides: list[str] | None = None,
    defaults_path: str | Path | None = None,
) -> tuple[dict[str, Any], str]:
    resolved = resolve_config(
        experiment_config_path=experiment_config_path,
        model_profile_path=model_profile_path,
        cli_overrides=cli_overrides,
        defaults_path=defaults_path,
    )
    return resolved, config_hash(resolved)


def _inject_prompt_resolution_metadata(config: dict[str, Any]) -> None:
    strategy = config.get("strategy")
    if not isinstance(strategy, dict):
        return

    raw_prompt_id = strategy.get("system_prompt_id", DEFAULT_PROMPT_ID)
    requested_id = str(raw_prompt_id).strip() if isinstance(raw_prompt_id, str) else DEFAULT_PROMPT_ID
    if not requested_id:
        requested_id = DEFAULT_PROMPT_ID

    resolution = resolve_system_prompt(
        system_prompt_id=requested_id,
        variables={},
        custom_template=(strategy.get("system_prompt_template") if isinstance(strategy.get("system_prompt_template"), str) else None),
    )
    strategy["system_prompt_id_effective"] = resolution.effective_id

    if resolution.fallback_applied:
        strategy["system_prompt_id_requested"] = resolution.requested_id
        strategy["system_prompt_id"] = resolution.effective_id
    else:
        strategy["system_prompt_id"] = resolution.requested_id
