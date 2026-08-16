"""Experiment manifest v1alpha1 (design §17).

Three representations exist: the source manifest (what the author wrote), the
resolved manifest (defaults, plugin versions, capability decisions, pricing
snapshot, expanded conditions, applied patches — immutable) and the runtime
snapshot (environment, packages, engine). YAML is authorship-only; the
canonical JSON form is what gets hashed.
"""

from __future__ import annotations

import itertools
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import hash_canonical
from .errors import ManifestValidationError, PatchApplicationError
from .events import JsonValue
from .knowledge import KnowledgePacket
from .versions import MANIFEST_API

NameStr = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")]
TagStr = Annotated[str, Field(min_length=1, max_length=64)]
HStr = Annotated[str, Field(pattern=r"^H[0-7]$")]
KStr = Annotated[str, Field(pattern=r"^K[0-7]$")]


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NameStr
    tags: tuple[TagStr, ...] = ()


class PluginRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin: NameStr
    version: str | None = None
    config: dict[str, JsonValue] = {}


class MatrixSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["product", "zip"] = "product"
    parameters: dict[str, tuple[JsonValue, ...]] = {}

    @model_validator(mode="after")
    def _non_empty(self) -> MatrixSpec:
        if any(not values for values in self.parameters.values()):
            raise ValueError("matrix parameters must not be empty")
        return self


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin: NameStr
    version: str | None = None
    config: dict[str, JsonValue] = {}
    config_from_matrix: tuple[str, ...] = ()


class PlayerModelSpec(BaseModel):
    """A player driven by a model through a decision strategy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str | None = None
    backend: str | None = None
    provider: str | None = None
    strategy: str | None = None
    from_matrix: tuple[str, ...] = ()


class PlayerPolicySpec(BaseModel):
    """A player driven by a fixed policy plugin (e.g. random legal)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin: NameStr
    version: str | None = None
    config: dict[str, JsonValue] = {}


class PlayerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: PlayerModelSpec | None = None
    policy: PlayerPolicySpec | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> PlayerSpec:
        if (self.model is None) == (self.policy is None):
            raise ValueError("player must define exactly one of: model, policy")
        return self


class RetrySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transport: int = Field(default=0, ge=0)
    parse: int = Field(default=0, ge=0)
    illegal: int = Field(default=0, ge=0)
    strategic: int = Field(default=0, ge=0)
    feedback: str = "legality_only"


class PromptOverrideSpec(BaseModel):
    """Protocol-level prompt controls: persona framing and few-shot examples.

    Enters the protocol identity hash; strategies apply it deterministically.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    system_instructions: str = ""
    examples: tuple[dict[str, str], ...] = ()


class ProtocolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    declared_assistance: HStr
    declared_knowledge: KStr = "K0"
    observation: dict[str, JsonValue] = {}
    retries: RetrySpec = RetrySpec()
    knowledge_packets: tuple[str, ...] = ()
    prompt: PromptOverrideSpec = PromptOverrideSpec()


class BudgetSpecManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_calls: int | None = Field(default=None, ge=1)
    max_input_tokens: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, ge=0)
    max_total_tokens: int | None = Field(default=None, ge=0)
    max_usd: float | None = Field(default=None, ge=0)
    max_wall_time_seconds: int | None = Field(default=None, ge=1)
    max_failed_calls: int | None = Field(default=None, ge=0)
    max_concurrent_episodes: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    per_call_timeout_seconds: int | None = Field(default=None, ge=1)


class EvaluationRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin: NameStr
    version: str | None = None
    config: dict[str, JsonValue] = {}


class ArtifactsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_requests: bool = False
    raw_responses: bool = False
    redact: Literal["none", "standard", "strict"] = "standard"


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = Field(ge=0)
    matrix: MatrixSpec = MatrixSpec()
    task: TaskSpec
    players: dict[Literal["white", "black"], PlayerSpec]
    protocol: ProtocolSpec
    budget: BudgetSpecManifest = BudgetSpecManifest()
    evaluation: tuple[EvaluationRef, ...] = ()
    artifacts: ArtifactsSpec = ArtifactsSpec()


class SourceManifest(BaseModel):
    """The author-facing document. Frozen and hashable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_version: Literal["zgw.dev/v1alpha1"] = MANIFEST_API
    kind: Literal["Experiment"] = "Experiment"
    metadata: Metadata
    spec: Spec

    def protocol_identity_hash(self) -> str:
        """Hash of everything that changes observed behavior (no timestamps)."""
        return hash_canonical(
            {
                "api_version": self.api_version,
                "kind": self.kind,
                "metadata": self.metadata.model_dump(mode="json"),
                "spec": self.spec.model_dump(mode="json"),
            }
        )

    def to_json_string(self) -> str:
        from .canonical import canonical_json_string

        return canonical_json_string(self.model_dump(mode="json"))


class ManifestPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(pattern=r"^/(spec|metadata)/[a-zA-Z0-9_/.-]+$")
    value: JsonValue

    def apply(self, source: SourceManifest) -> SourceManifest:
        """Apply the patch over the source model, then re-validate."""
        data: dict[str, Any] = source.model_dump(mode="json")
        parts = [p for p in self.path.split("/") if p]
        current: Any = data
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                raise PatchApplicationError(
                    f"patch path {self.path!r} does not exist",
                    technical_context=f"missing segment {part!r}",
                )
            current = cast(Any, current[part])
        leaf = parts[-1]
        if not isinstance(current, dict):
            raise PatchApplicationError(f"patch path {self.path!r} does not point into an object")
        if leaf not in current:
            raise PatchApplicationError(
                f"patch path {self.path!r} does not exist",
                technical_context=f"missing leaf {leaf!r}",
            )
        current[leaf] = self.value
        try:
            return SourceManifest.model_validate(data)
        except Exception as exc:
            raise PatchApplicationError(
                f"patch {self.path!r} produced an invalid manifest",
                technical_context=str(exc),
            ) from exc


class ResolvedCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str
    index: int
    parameters: dict[str, JsonValue]
    task: TaskSpec
    players: dict[Literal["white", "black"], PlayerSpec]
    protocol: ProtocolSpec
    budget: BudgetSpecManifest
    evaluation: tuple[EvaluationRef, ...]
    artifacts: ArtifactsSpec


class PluginSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin_id: str
    version: str | None = None
    distribution: str | None = None
    api: str


class PriceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    source: str = "manual"
    effective_from: str | None = None


class PricingSnapshot(BaseModel):
    """Frozen price registry view. GATE-009 pending means cost stays unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_version: str = "unset"
    entries: tuple[PriceEntry, ...] = ()
    cost_status: Literal["unknown", "snapshot"] = "unknown"


class ResolvedManifest(BaseModel):
    """The immutable compilation of a source manifest (design §6.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_version: Literal["zgw.dev/v1alpha1"] = MANIFEST_API
    experiment_name: str
    source_hash: str
    source: SourceManifest
    patches: tuple[ManifestPatch, ...] = ()
    conditions: tuple[ResolvedCondition, ...]
    plugin_snapshots: tuple[PluginSnapshot, ...] = ()
    pricing_snapshot: PricingSnapshot = PricingSnapshot()
    warnings: tuple[str, ...] = ()
    protocol_hash: str
    knowledge_packets: tuple[KnowledgePacket, ...] = ()

    def packets_for(self, condition: ResolvedCondition) -> tuple[KnowledgePacket, ...]:
        """Resolved packets referenced by one condition, in declaration order."""
        wanted = set(condition.protocol.knowledge_packets)
        return tuple(p for p in self.knowledge_packets if p.id in wanted)

    def condition_by_id(self, condition_id: str) -> ResolvedCondition | None:
        for condition in self.conditions:
            if condition.condition_id == condition_id:
                return condition
        return None


def expand_matrix(experiment_name: str, spec: Spec) -> tuple[ResolvedCondition, ...]:
    """Deterministic product/zip expansion with stable per-condition IDs.

    Condition IDs derive from the canonical hash of their parameter bindings,
    so reordering matrix entries never renumbers conditions.
    """
    names = list(spec.matrix.parameters.keys())
    values_lists = [spec.matrix.parameters[name] for name in names]
    if not values_lists:
        # A matrix with no dimensions is a single implicit condition.
        condition_id = (
            f"cnd_{hash_canonical({'experiment': experiment_name, 'parameters': {}})[:16]}"
        )
        return (
            ResolvedCondition(
                condition_id=condition_id,
                index=0,
                parameters={},
                task=spec.task,
                players=spec.players,
                protocol=spec.protocol,
                budget=spec.budget,
                evaluation=spec.evaluation,
                artifacts=spec.artifacts,
            ),
        )
    if spec.matrix.mode == "zip":
        lengths = {len(values) for values in values_lists}
        if len(lengths) > 1:
            raise ManifestValidationError(
                "zip matrix requires all dimensions to have the same length",
                technical_context=f"lengths={sorted(lengths)}",
            )
        combinations = zip(*values_lists, strict=True)
    else:
        combinations = itertools.product(*values_lists)

    conditions: list[ResolvedCondition] = []
    for index, combo in enumerate(combinations):
        parameters = dict(zip(names, combo, strict=True))
        condition_id = (
            f"cnd_{hash_canonical({'experiment': experiment_name, 'parameters': parameters})[:16]}"
        )
        conditions.append(
            ResolvedCondition(
                condition_id=condition_id,
                index=index,
                parameters=parameters,
                task=_bind_task_config(spec.task, parameters),
                players=_bind_matrix_players(spec.players, parameters),
                protocol=spec.protocol,
                budget=spec.budget,
                evaluation=spec.evaluation,
                artifacts=spec.artifacts,
            )
        )
    return tuple(conditions)


def _bind_task_config(task: TaskSpec, parameters: dict[str, JsonValue]) -> TaskSpec:
    """Bind task config keys listed in ``config_from_matrix`` (FR-006)."""
    if not task.config_from_matrix:
        return task
    config = dict(task.config)
    for key in task.config_from_matrix:
        if key in parameters:
            config[key] = parameters[key]
    return task.model_copy(update={"config": config})


def _bind_matrix_players(
    players: dict[Literal["white", "black"], PlayerSpec],
    parameters: dict[str, JsonValue],
) -> dict[Literal["white", "black"], PlayerSpec]:
    """Bind ``from_matrix`` references to expanded parameter values (FR-006)."""
    bound: dict[Literal["white", "black"], PlayerSpec] = {}
    for side, player in players.items():
        if player.model is None or not player.model.from_matrix:
            bound[side] = player
            continue
        model = player.model
        values: dict[str, Any] = model.model_dump()
        for field_name in ("strategy", "backend", "provider", "model"):
            if field_name in model.from_matrix and field_name in parameters:
                values[field_name] = str(parameters[field_name])
        bound[side] = PlayerSpec.model_validate({"model": values})
    return bound


def resolve_manifest(
    source: SourceManifest,
    *,
    patches: tuple[ManifestPatch, ...] = (),
    plugin_snapshots: tuple[PluginSnapshot, ...] = (),
    pricing_snapshot: PricingSnapshot | None = None,
    warnings: tuple[str, ...] = (),
    knowledge_packets: tuple[KnowledgePacket, ...] = (),
) -> ResolvedManifest:
    """Compile a source manifest into an immutable resolved manifest."""
    patched = source
    for patch in patches:
        patched = patch.apply(patched)
    conditions = expand_matrix(patched.metadata.name, patched.spec)
    identity = {
        "source": patched.model_dump(mode="json"),
        "patches": [p.model_dump(mode="json") for p in patches],
        "plugin_snapshots": [p.model_dump(mode="json") for p in plugin_snapshots],
        "pricing_registry_version": (
            pricing_snapshot.registry_version if pricing_snapshot is not None else "unset"
        ),
        "knowledge_packets": [
            {"id": p.id, "content_hash": p.content_hash} for p in knowledge_packets
        ],
    }
    protocol_hash = hash_canonical(identity)
    return ResolvedManifest(
        experiment_name=patched.metadata.name,
        source_hash=patched.protocol_identity_hash(),
        source=patched,
        patches=patches,
        conditions=conditions,
        plugin_snapshots=plugin_snapshots,
        pricing_snapshot=pricing_snapshot if pricing_snapshot is not None else PricingSnapshot(),
        warnings=warnings,
        protocol_hash=protocol_hash,
        knowledge_packets=knowledge_packets,
    )
