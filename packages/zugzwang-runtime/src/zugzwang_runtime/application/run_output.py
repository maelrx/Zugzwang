"""Run output writer (M0).

Writes the per-run directory under the workspace: resolved manifest, event
stream (JSONL), artifacts, metrics placeholder and a checksum manifest
(design §11.2). M1 moves state into SQLite; these files remain the
audit-friendly per-run export.
"""

from __future__ import annotations

import json

from zugzwang_core.domain.canonical import sha256_hex
from zugzwang_core.domain.events import EventEnvelope
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest

from ..execution.artifacts import ArtifactStore
from ..execution.coordinator import RunOutcome
from ..workspace import Workspace


def write_run_output(
    *,
    workspace: Workspace,
    resolved: ResolvedManifest,
    condition: ResolvedCondition,
    outcome: RunOutcome,
    artifact_store: ArtifactStore,
) -> str:
    run_dir = workspace.run_dir(outcome.run_id)
    artifacts_dir = run_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=False)
    artifacts_dir.mkdir(parents=True, exist_ok=False)

    resolved_path = run_dir / "manifest.resolved.json"
    resolved_path.write_text(resolved.model_dump_json(indent=2), encoding="utf-8")

    events_path = run_dir / "events.jsonl"
    lines = [event.to_json_line() for event in outcome.events]
    events_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    checksums: dict[str, str] = {}
    for event in outcome.events:
        for ref_id in event.artifact_refs:
            if ref_id.startswith("sha256:"):
                digest = ref_id.split(":", 1)[1]
                try:
                    ref = _ref_from_id(ref_id)
                    payload = artifact_store.get(ref)
                except Exception:
                    continue
                target = artifacts_dir / ref.storage_path()
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_bytes(payload.data)
                checksums[target.relative_to(run_dir).as_posix()] = digest

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "status": "m0",
                "budget_used": outcome.budget_used,
                "episodes": [
                    {
                        "episode_id": e.episode_id,
                        "outcome": e.outcome,
                        "steps_committed": e.steps_committed,
                        "effective_h": e.effective_h,
                        "effective_k": e.effective_k,
                    }
                    for e in outcome.episodes
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    for rel_path in ("manifest.resolved.json", "events.jsonl", "metrics.json"):
        data = (run_dir / rel_path).read_bytes()
        checksums[rel_path] = sha256_hex(data)

    checksum_lines = [f"{digest}  {path}" for path, digest in sorted(checksums.items())]
    (run_dir / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + ("\n" if checksum_lines else ""), encoding="utf-8"
    )
    return str(run_dir)


def _ref_from_id(ref_id: str):
    from zugzwang_core.domain.artifacts import ArtifactRef

    return ArtifactRef.parse(ref_id)


def serialize_event(event: EventEnvelope) -> str:
    return event.to_json_line()
