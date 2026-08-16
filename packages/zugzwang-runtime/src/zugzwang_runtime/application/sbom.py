"""SBOM export (CycloneDX) from the uv lockfile (design §20.9).

Release supply chain: locked dependencies, hashes and licenses go into a
CycloneDX 1.5 JSON document. No network access.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast


def export_cyclonedx(lock_path: Path, project_root: Path) -> dict[str, Any]:
    lock_data: dict[str, Any] = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages: list[dict[str, Any]] = []
    for pkg in cast(list[dict[str, Any]], lock_data.get("package", [])):
        name = str(pkg.get("name", "unknown"))
        version = str(pkg.get("version", ""))
        entry: dict[str, Any] = {
            "type": "library",
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "name": name,
            "version": version,
        }
        source = cast(dict[str, Any] | None, pkg.get("source"))
        if isinstance(source, dict) and source.get("virtual"):
            entry["bom-ref"] = f"pkg:pypi/{name}@virtual"
        packages.append(entry)
    bom: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-0000-0000-000000000001",
        "version": 1,
        "components": packages,
    }
    return bom


def write_sbom(project_root: Path, output: Path) -> Path:
    lock_path = project_root / "uv.lock"
    if not lock_path.exists():
        raise FileNotFoundError("uv.lock not found; run `uv lock` first")
    bom = export_cyclonedx(lock_path, project_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bom, indent=2, ensure_ascii=False), encoding="utf-8")
    return output
