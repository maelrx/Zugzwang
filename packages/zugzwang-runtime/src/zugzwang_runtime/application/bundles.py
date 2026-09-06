"""Run bundle export/import and garbage collection (design §11.8, §11.9, FR-039).

A bundle is self-contained: manifests, events, artifacts, metrics and a
checksum manifest. Import validates schema and checksums before registering.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from zugzwang_core.domain.artifacts import ArtifactRef
from zugzwang_core.domain.canonical import sha256_hex
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.errors import ArtifactError, SecurityError
from zugzwang_core.domain.versions import BUNDLE_API

from ..artifacts.cas import ContentAddressedStore
from ..persistence.repositories import (
    ArtifactRepository,
    EpisodeRepository,
    EvaluationRunRepository,
    EventRepository,
    MetricObservationRepository,
    RunRepository,
    StepRepository,
)

_BUNDLE_IGNORED_NAMES = {"checksums.sha256"}


class BundleManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = BUNDLE_API
    bundle_id: str
    run_id: str
    created_at: str
    protocol_hash: str
    completeness: dict[str, bool]
    redactions: dict[str, str | bool]
    reproducibility: dict[str, bool | list[str]]
    declared_assistance: str
    effective_assistance: str
    assistance_violated: bool = False
    evaluation_generations: int = 0
    selected_evaluation_run_id: str | None = None
    checksums_file: str = "checksums.sha256"


class ExportRunBundleService:
    def __init__(
        self,
        *,
        runs: RunRepository,
        episodes: EpisodeRepository,
        steps: StepRepository,
        metrics: MetricObservationRepository,
        events: EventRepository,
        artifacts: ArtifactRepository,
        cas: ContentAddressedStore,
        run_dir: Path,
        evaluation_runs: EvaluationRunRepository | None = None,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._metrics = metrics
        self._events = events
        self._artifacts = artifacts
        self._cas = cas
        self._run_dir = run_dir
        self._evaluation_runs = evaluation_runs or EvaluationRunRepository(metrics.engine)

    def export(self, run_id: str, output: Path) -> Path:
        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        output.mkdir(parents=True, exist_ok=False)
        artifacts_dir = output / "artifacts"
        artifacts_dir.mkdir(parents=True)

        referenced: set[str] = set()
        for field in ("resolved_manifest_artifact_id",):
            if row.get(field):
                referenced.add(str(row[field]))
        for episode in self._episodes.for_run(run_id):
            for field in ("initial_state_artifact_id", "final_state_artifact_id"):
                if episode.get(field):
                    referenced.add(str(episode[field]))
            for step in self._steps.for_episode(episode["episode_id"]):
                for field in (
                    "observation_artifact_id",
                    "decision_trace_artifact_id",
                    "transition_artifact_id",
                    "search_graph_artifact_id",
                ):
                    if step.get(field):
                        referenced.add(str(step[field]))
        event_rows = self._events.for_run(run_id)
        lines: list[str] = []
        for event in event_rows:
            refs: list[Any] = list(event.get("artifact_refs_json") or [])
            referenced.update(str(r) for r in refs)
            lines.append(
                json.dumps(
                    {
                        "schema_version": "zgw.event/v1alpha1",
                        "event_id": event["event_id"],
                        "event_type": event["event_type"],
                        "event_version": event["event_version"],
                        "occurred_at": event["occurred_at"],
                        "stream": {
                            "type": event["stream_type"],
                            "id": event["stream_id"],
                            "sequence": event["sequence_no"],
                        },
                        "context": {
                            "run_id": event["run_id"],
                            "episode_id": event["episode_id"],
                            "step_id": event["step_id"],
                            "attempt_id": event["attempt_id"],
                        },
                        "payload": event["payload_json"],
                        "artifact_refs": event["artifact_refs_json"],
                    },
                    ensure_ascii=False,
                )
            )
        (output / "events.jsonl").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

        checksums: dict[str, str] = {}
        for ref_id in sorted(referenced):
            if not ref_id.startswith("sha256:"):
                continue
            try:
                payload = self._cas.get(ArtifactRef.parse(ref_id))
            except ArtifactError:
                continue
            target = artifacts_dir / ArtifactRef.parse(ref_id).storage_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload.data)
            checksums[f"artifacts/{ArtifactRef.parse(ref_id).storage_path()}"] = ref_id.split(
                ":", 1
            )[1]

        if self._run_dir.exists():
            for path in sorted(self._run_dir.rglob("*")):
                if path.is_file() and path.name not in _BUNDLE_IGNORED_NAMES:
                    rel = path.relative_to(self._run_dir).as_posix()
                    target = output / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        shutil.copy2(path, target)
                    checksums[rel] = sha256_hex(path.read_bytes())

        metrics_rows = self._metrics.for_run(run_id)
        for metric in metrics_rows:
            if metric.get("provenance_artifact_id"):
                referenced.add(str(metric["provenance_artifact_id"]))
        (output / "metrics.json").write_text(
            json.dumps([dict(m) for m in metrics_rows], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        checksums["metrics.json"] = sha256_hex((output / "metrics.json").read_bytes())
        checksums["events.jsonl"] = sha256_hex((output / "events.jsonl").read_bytes())
        evaluations = self._evaluation_runs.for_run(run_id)
        (output / "evaluation_runs.json").write_text(
            json.dumps(evaluations, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        checksums["evaluation_runs.json"] = sha256_hex(
            (output / "evaluation_runs.json").read_bytes()
        )

        artifact_rows = {
            str(artifact_id): artifact
            for artifact_id in referenced
            if (artifact := self._artifacts.get(str(artifact_id))) is not None
        }

        bundle = BundleManifest(
            bundle_id=f"bundle_{run_id}",
            run_id=run_id,
            created_at=to_iso_z(utc_now()),
            protocol_hash=row["protocol_hash"],
            completeness={
                "source_manifest": False,
                "resolved_manifest": bool(row.get("resolved_manifest_artifact_id")),
                "events": True,
                "raw_requests": any(
                    artifact["media_type"].endswith("model-request+json")
                    for artifact in artifact_rows.values()
                ),
                "raw_responses": any(
                    artifact["media_type"].endswith("model-response+json")
                    for artifact in artifact_rows.values()
                ),
                "metrics": True,
                "environment_snapshots": True,
                "observation_artifacts": any(
                    artifact["media_type"].endswith("observation+json")
                    for artifact in artifact_rows.values()
                ),
                "decision_traces": any(
                    artifact["media_type"].endswith("decision-trace+json")
                    for artifact in artifact_rows.values()
                ),
                "reasoning_telemetry": any(
                    artifact["media_type"].endswith("reasoning-telemetry+json")
                    for artifact in artifact_rows.values()
                ),
                "evaluation_runs": True,
            },
            redactions={"policy": "standard/v1", "content_removed": False},
            reproducibility={
                "auditability": True,
                "offline_replay": True,
                "rerunnable": True,
                "deterministic": False,
                "limitations": ["remote provider snapshot may change"],
            },
            declared_assistance=row["declared_assistance"],
            effective_assistance=row.get("effective_assistance") or "H2",
            assistance_violated=bool(row.get("assistance_violated", 0)),
            evaluation_generations=len(evaluations),
            selected_evaluation_run_id=(
                evaluations[0]["evaluation_run_id"] if evaluations else None
            ),
        )
        (output / "bundle.json").write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        checksums["bundle.json"] = sha256_hex((output / "bundle.json").read_bytes())

        checksum_lines = [f"{digest}  {rel}" for rel, digest in sorted(checksums.items())]
        (output / "checksums.sha256").write_text(
            "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
            encoding="utf-8",
        )
        return output


class ImportRunBundleService:
    """Validates and imports a bundle into a workspace (schema + checksums)."""

    def __init__(
        self,
        *,
        cas: ContentAddressedStore,
        artifacts: ArtifactRepository,
        evaluation_runs: EvaluationRunRepository | None = None,
    ) -> None:
        self._cas = cas
        self._artifacts = artifacts
        self._evaluation_runs = evaluation_runs

    def import_bundle(self, bundle_dir: Path) -> dict[str, str]:
        bundle_path = bundle_dir / "bundle.json"
        if not bundle_path.exists():
            raise SecurityError(f"{bundle_dir} is not a valid bundle: bundle.json missing")
        bundle = BundleManifest.model_validate(json.loads(bundle_path.read_text(encoding="utf-8")))
        if bundle.schema_version != BUNDLE_API:
            raise SecurityError(f"unsupported bundle schema {bundle.schema_version!r}")
        self._verify_checksums(bundle_dir)
        imported = 0
        imported_evaluations = 0
        artifacts_dir = bundle_dir / "artifacts"
        if artifacts_dir.exists():
            for path in artifacts_dir.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(artifacts_dir).as_posix()
                parts = rel.split("/")
                if len(parts) != 2 or len(parts[0]) != 2:
                    raise SecurityError(f"suspicious artifact path {rel!r}")
                digest = parts[0] + parts[1]
                ref = ArtifactRef(digest=digest, media_type="application/octet-stream")
                data = path.read_bytes()
                if sha256_hex(data) != digest:
                    raise ArtifactError(f"bundle artifact {rel} failed checksum verification")
                from zugzwang_core.domain.artifacts import ArtifactPayload

                self._cas.put(ArtifactPayload(media_type="application/octet-stream", data=data))
                self._artifacts.insert_artifact(
                    {
                        "artifact_id": ref.as_id(),
                        "algorithm": "sha256",
                        "size_bytes": len(data),
                        "media_type": "application/octet-stream",
                        "relative_path": ref.storage_path(),
                        "created_at": to_iso_z(utc_now()),
                    }
                )
                imported += 1
        evaluations_path = bundle_dir / "evaluation_runs.json"
        if evaluations_path.exists() and self._evaluation_runs is not None:
            evaluations = json.loads(evaluations_path.read_text(encoding="utf-8"))
            if not isinstance(evaluations, list):
                raise SecurityError("evaluation_runs.json must contain a list")
            evaluation_rows = cast(list[Any], evaluations)
            for raw in evaluation_rows:
                if not isinstance(raw, dict):
                    raise SecurityError("evaluation_runs.json contains a non-object")
                self._evaluation_runs.insert(cast(dict[str, Any], raw))
                imported_evaluations += 1
        return {
            "bundle_id": bundle.bundle_id,
            "run_id": bundle.run_id,
            "artifacts_imported": str(imported),
            "evaluation_runs_imported": str(imported_evaluations),
        }

    @staticmethod
    def _verify_checksums(bundle_dir: Path) -> None:
        checksums_file = bundle_dir / "checksums.sha256"
        if not checksums_file.exists():
            raise SecurityError("bundle has no checksums.sha256")
        for line in checksums_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            target = bundle_dir / rel
            if not target.exists():
                raise ArtifactError(f"bundle file {rel} is missing")
            actual = sha256_hex(target.read_bytes())
            if actual != digest:
                raise ArtifactError(f"bundle file {rel} failed checksum verification")


class GarbageCollector:
    """Removes CAS objects not referenced by any projection or event (FR-039)."""

    def __init__(self, *, cas: ContentAddressedStore, artifacts: ArtifactRepository) -> None:
        self._cas = cas
        self._artifacts = artifacts

    def collect(self, *, dry_run: bool = True) -> dict[str, Any]:
        referenced = self._artifacts.referenced_ids()
        orphans: list[str] = []
        for ref in self._cas.walk():
            if ref.as_id() not in referenced:
                orphans.append(ref.as_id())
                if not dry_run:
                    self._cas.delete(ref)
        return {"dry_run": dry_run, "orphans_found": len(orphans), "orphans": orphans}
