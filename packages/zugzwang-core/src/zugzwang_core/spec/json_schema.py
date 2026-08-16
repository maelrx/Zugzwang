"""JSON Schema export (design §17.1, FR-003).

Schemas are generated from the strict Pydantic models, so code and contract
cannot drift. Output uses JSON Schema Draft 2020-12.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from ..domain.events import EventEnvelope
from ..domain.manifests import ResolvedManifest, SourceManifest
from ..ports.evaluator import MetricDefinition, MetricObservation
from ..ports.model import ModelRequest
from ..ports.plugin import PluginDescriptor

SCHEMA_TARGETS: dict[str, Any] = {
    "experiment-manifest": SourceManifest,
    "experiment-manifest-resolved": ResolvedManifest,
    "event": EventEnvelope,
    "metric-observation": MetricObservation,
    "metric-definition": MetricDefinition,
    "model-request": ModelRequest,
    "plugin-descriptor": PluginDescriptor,
}

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ROOT_ID = "https://zugzwang.dev/schemas"


def generate_json_schemas() -> dict[str, dict[str, Any]]:
    """Generate versioned JSON Schemas for the v1alpha1 contract family."""
    result: dict[str, dict[str, Any]] = {}
    for name, model in SCHEMA_TARGETS.items():
        schema: dict[str, Any] = TypeAdapter(model).json_schema()
        schema["$schema"] = SCHEMA_DRAFT
        schema["$id"] = f"{SCHEMA_ROOT_ID}/{name}/v1alpha1"
        result[name] = schema
    return result
