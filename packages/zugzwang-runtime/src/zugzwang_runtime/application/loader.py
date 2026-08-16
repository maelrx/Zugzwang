"""Manifest loading: YAML authorship → strict Pydantic validation.

Errors carry path, offending value, schema location and a suggestion
(FR-002). No YAML custom tags, no environment interpolation (design §17.1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

from zugzwang_core.domain.errors import ManifestValidationError
from zugzwang_core.domain.manifests import SourceManifest


class SafeYamlLoader(yaml.SafeLoader):
    """SafeLoader with a hard rejection of unknown tags."""

    def unknown(self, node: Any) -> None:  # type: ignore[override]
        raise ManifestValidationError(
            f"unsupported YAML tag {node.tag!r}",
            technical_context=f"line {node.start_mark.line + 1}",
        )


def _parse_yaml(text: str) -> Any:
    try:
        return yaml.load(text, Loader=SafeYamlLoader)
    except ManifestValidationError:
        raise
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        mark_line = getattr(mark, "line", None)
        mark_column = getattr(mark, "column", None)
        location = (
            f"line {mark_line + 1}, column {mark_column + 1}"
            if mark_line is not None and mark_column is not None
            else "unknown"
        )
        problem = getattr(exc, "problem", None)
        raise ManifestValidationError(
            f"invalid YAML: {problem or exc}",
            technical_context=location,
        ) from exc


def _suggestion_for(loc: tuple[Any, ...], error_type: Any, input_value: Any) -> str:
    if error_type == "missing":
        return f"add required field {'.'.join(str(p) for p in loc)}"
    if error_type == "literal_error":
        return f"allowed values are fixed; check the schema for {'.'.join(str(p) for p in loc)}"
    return f"check the manifest schema for {'.'.join(str(p) for p in loc)}"


def format_pydantic_error(error: dict[str, Any]) -> str:
    loc = tuple(cast(tuple[Any, ...], error.get("loc", ())))
    error_type = error.get("type", "value_error")
    value = error.get("input")
    msg = error.get("msg", "")
    if not loc:
        return f"manifest is invalid: {msg}"
    path = "$." + ".".join(str(p) for p in loc)
    suggestion = _suggestion_for(loc, error_type, value)
    value_repr = repr(value) if not isinstance(value, (dict, list)) else "<object>"
    return f"{path}: {msg} (got {value_repr}). Suggestion: {suggestion}"


def load_source_manifest(path: Path) -> tuple[SourceManifest, str]:
    """Read a manifest file and validate it strictly."""
    if not path.exists():
        raise ManifestValidationError(
            f"manifest not found: {path}",
            technical_context=str(path),
        )
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestValidationError(
            f"cannot read manifest {path}",
            technical_context=str(exc),
        ) from exc

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        data = _parse_yaml(raw_text)
    elif suffix == ".json":
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ManifestValidationError(
                f"invalid JSON in {path}: {exc.msg}",
                technical_context=f"line {exc.lineno}, column {exc.colno}",
            ) from exc
    else:
        raise ManifestValidationError(
            f"unsupported manifest format {suffix!r} (use .yaml, .yml or .json)",
            technical_context=str(path),
        )

    if not isinstance(data, dict):
        raise ManifestValidationError(
            "manifest root must be an object",
            technical_context=f"got {type(data).__name__}",
        )

    try:
        manifest = SourceManifest.model_validate(data)
    except Exception as exc:
        errors = getattr(exc, "errors", None)
        details = [format_pydantic_error(e) for e in errors()] if errors is not None else [str(exc)]
        raise ManifestValidationError(
            f"manifest {path} is invalid:\n  - " + "\n  - ".join(details),
            technical_context=str(path),
        ) from exc
    return manifest, raw_text


def manifest_to_yaml(manifest: SourceManifest) -> str:
    """Serialize a manifest back to YAML (for run-dir source preservation)."""

    data = json.loads(manifest.to_json_string())
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
