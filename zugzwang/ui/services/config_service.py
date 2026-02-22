from __future__ import annotations

from pathlib import Path
from typing import Any

from zugzwang.experiments.runner import ExperimentRunner
from zugzwang.infra.config import resolve_with_hash
from zugzwang.ui.services.paths import project_root
from zugzwang.ui.types import ConfigTemplate, ResolvedConfigPreview, ValidationResult


class ConfigService:
    def __init__(self, config_root: str | Path | None = None) -> None:
        self.config_root = Path(config_root) if config_root else project_root() / "configs"

    def list_templates(self) -> list[ConfigTemplate]:
        templates: list[ConfigTemplate] = []
        for category in ("baselines", "ablations"):
            category_path = self.config_root / category
            if not category_path.exists():
                continue
            for config_path in sorted(category_path.glob("*.yaml")):
                templates.append(
                    ConfigTemplate(
                        name=config_path.stem,
                        path=str(config_path),
                        category=category,
                    )
                )
        return templates

    def resolve_config_preview(
        self,
        config_path: str | Path,
        overrides: str | list[str] | None = None,
        model_profile: str | Path | None = None,
    ) -> ResolvedConfigPreview:
        parsed_overrides = self.parse_overrides(overrides)
        runner = ExperimentRunner(
            config_path=self._resolve_path(config_path),
            model_profile_path=self._resolve_optional_path(model_profile),
            overrides=parsed_overrides,
        )
        prepared = runner.prepare()
        return ResolvedConfigPreview(
            config_path=str(self._resolve_path(config_path)),
            config_hash=prepared.config_hash,
            run_id=prepared.run_id,
            scheduled_games=prepared.scheduled_games,
            estimated_total_cost_usd=prepared.estimated_total_cost_usd,
            resolved_config=prepared.config,
        )

    def validate_config(
        self,
        config_path: str | Path,
        overrides: str | list[str] | None = None,
        model_profile: str | Path | None = None,
    ) -> ValidationResult:
        parsed_overrides = self.parse_overrides(overrides)
        try:
            resolved, cfg_hash = resolve_with_hash(
                experiment_config_path=self._resolve_path(config_path),
                model_profile_path=self._resolve_optional_path(model_profile),
                cli_overrides=parsed_overrides,
            )
        except Exception as exc:
            return ValidationResult(ok=False, message=str(exc), config_hash=None, resolved_config=None)

        return ValidationResult(
            ok=True,
            message="Config is valid",
            config_hash=cfg_hash,
            resolved_config=resolved,
        )

    def resolve_path(self, value: str | Path) -> Path:
        return self._resolve_path(value)

    def resolve_optional_path(self, value: str | Path | None) -> Path | None:
        return self._resolve_optional_path(value)

    @staticmethod
    def parse_overrides(raw: str | list[str] | None) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            lines = raw
        else:
            lines = raw.splitlines()

        parsed: list[str] = []
        for line in lines:
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.startswith("#"):
                continue
            parsed.append(candidate)
        return parsed

    def _resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        candidate = project_root() / path
        if candidate.exists():
            return candidate
        return path

    def _resolve_optional_path(self, value: str | Path | None) -> Path | None:
        if value is None:
            return None
        stripped = str(value).strip()
        if not stripped:
            return None
        return self._resolve_path(stripped)
