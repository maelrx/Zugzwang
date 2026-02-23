from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any
import uuid

from zugzwang.api.services.config_service import ConfigService
from zugzwang.api.services.paths import ui_jobs_root
from zugzwang.api.services.run_service import RunService
from zugzwang.experiments.scheduler import (
    BatchState,
    BatchStepDefinition,
    SchedulerError,
    advance_batch_state,
    batch_from_dict,
    build_batch_state,
    cancel_batch,
    is_batch_terminal,
    normalize_step_definitions,
)
from zugzwang.infra.ids import timestamp_utc


class SchedulerService:
    def __init__(
        self,
        *,
        store_root: str | Path | None = None,
        run_service: RunService | None = None,
        config_service: ConfigService | None = None,
    ) -> None:
        self.store_root = Path(store_root) if store_root else ui_jobs_root() / "scheduler"
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.run_service = run_service or RunService()
        self.config_service = config_service or ConfigService()

    def create_batch(
        self,
        *,
        steps: list[dict[str, Any]],
        fail_fast: bool = True,
        dry_run: bool = False,
        batch_id: str | None = None,
    ) -> dict[str, Any]:
        definitions = normalize_step_definitions(steps)
        previews = self._build_step_previews(definitions)

        resolved_batch_id = _normalize_batch_id(batch_id) or self._make_batch_id()
        batch = build_batch_state(
            batch_id=resolved_batch_id,
            definitions=definitions,
            fail_fast=fail_fast,
            dry_run=dry_run,
            previews=previews,
        )

        if not dry_run:
            batch = self._advance_batch(batch)
        self._save_batch(batch)
        return batch.to_dict()

    def list_batches(self, *, limit: int = 50, refresh: bool = True) -> list[dict[str, Any]]:
        paths = sorted(
            self.store_root.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        items: list[dict[str, Any]] = []
        for path in paths[: max(1, limit)]:
            batch = self._load_batch(path.stem)
            if refresh:
                batch = self._advance_batch(batch)
                self._save_batch(batch)
            items.append(batch.to_dict())
        return items

    def get_batch(self, batch_id: str, *, refresh: bool = True) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        if refresh:
            batch = self._advance_batch(batch)
            self._save_batch(batch)
        return batch.to_dict()

    def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        if not is_batch_terminal(batch):
            for step in batch.steps:
                if step.status == "running" and step.job_id:
                    self.run_service.cancel_run(step.job_id)
            batch = cancel_batch(batch)
            self._save_batch(batch)
        return batch.to_dict()

    def _build_step_previews(self, definitions: list[BatchStepDefinition]) -> dict[str, dict[str, Any]]:
        previews: dict[str, dict[str, Any]] = {}
        for definition in definitions:
            effective_overrides = list(definition.overrides)
            if definition.mode == "play":
                effective_overrides.extend(["experiment.target_valid_games=1", "experiment.max_games=1"])
            preview = self.config_service.resolve_config_preview(
                config_path=definition.config_path,
                overrides=effective_overrides,
                model_profile=definition.model_profile,
            )
            previews[definition.step_id] = {
                "config_path": preview.config_path,
                "config_hash": preview.config_hash,
                "run_id": preview.run_id,
                "scheduled_games": preview.scheduled_games,
                "estimated_total_cost_usd": preview.estimated_total_cost_usd,
            }
        return previews

    def _advance_batch(self, batch: BatchState) -> BatchState:
        if is_batch_terminal(batch):
            return batch

        updated = advance_batch_state(
            batch,
            fetch_job=lambda job_id: self.run_service.get_job(job_id, refresh=True),
            start_step=self._start_step,
        )
        return updated

    def _start_step(self, step: Any) -> dict[str, Any]:
        overrides = list(step.overrides or [])
        handle = self.run_service.start_run(
            config_path=step.config_path,
            model_profile=step.model_profile,
            overrides=overrides,
            mode=step.mode,
        )
        return _job_handle_to_dict(handle)

    def _make_batch_id(self) -> str:
        stamp = timestamp_utc().replace(":", "").replace("-", "")
        return f"batch-{stamp}-{uuid.uuid4().hex[:8]}"

    def _batch_path(self, batch_id: str) -> Path:
        normalized = _normalize_batch_id(batch_id)
        if not normalized:
            raise SchedulerError("batch_id must not be empty")
        return self.store_root / f"{normalized}.json"

    def _load_batch(self, batch_id: str) -> BatchState:
        path = self._batch_path(batch_id)
        if not path.exists():
            raise FileNotFoundError(f"Batch not found: {batch_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SchedulerError(f"Invalid batch payload: {path}")
        return batch_from_dict(payload)

    def _save_batch(self, batch: BatchState) -> None:
        path = self._batch_path(batch.batch_id)
        path.write_text(json.dumps(batch.to_dict(), indent=2), encoding="utf-8")


def _normalize_batch_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = value.strip()
    return parsed or None


def _job_handle_to_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        output = to_dict()
        if isinstance(output, dict):
            return output
    if is_dataclass(payload):
        output = asdict(payload)
        if isinstance(output, dict):
            return output
    raise SchedulerError(f"Unsupported job handle payload type: {type(payload)!r}")
