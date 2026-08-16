"""Unit tests: canonical hashing, assistance, events, manifests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from zugzwang_core.domain.assistance import (
    AssistanceDeclared,
    AssistanceImpact,
    HClass,
    KClass,
    audit_assistance,
    effective_assistance,
)
from zugzwang_core.domain.canonical import canonical_json_bytes, hash_canonical
from zugzwang_core.domain.errors import ManifestValidationError, PatchApplicationError
from zugzwang_core.domain.events import EventContext, EventEnvelope, EventStreamRef
from zugzwang_core.domain.manifests import (
    ManifestPatch,
    SourceManifest,
    expand_matrix,
    resolve_manifest,
)


@pytest.mark.unit
class TestCanonicalHashing:
    def test_key_order_irrelevant(self) -> None:
        assert hash_canonical({"a": 1, "b": [1, 2]}) == hash_canonical({"b": [1, 2], "a": 1})

    def test_types_distinguished(self) -> None:
        assert hash_canonical({"x": 1}) != hash_canonical({"x": "1"})
        assert hash_canonical([1]) != hash_canonical(["1"])

    def test_decimal_stable(self) -> None:
        assert hash_canonical({"d": Decimal("1.5")}) == hash_canonical({"d": "1.5"})

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError):
            canonical_json_bytes({"x": float("nan")})

    @given(st.dictionaries(st.text(alphabet="ab", max_size=4), st.integers(), max_size=5))
    def test_hash_idempotent(self, value: dict[str, int]) -> None:
        assert hash_canonical(value) == hash_canonical(value)


@pytest.mark.unit
class TestAssistance:
    def test_effective_is_max(self) -> None:
        impacts = (
            AssistanceImpact(h=HClass.H2, source="canonical_transition"),
            AssistanceImpact(h=HClass.H5, source="stockfish_score"),
        )
        assert effective_assistance(impacts) == (HClass.H5, KClass.K0)

    def test_violation_recorded_not_silent(self) -> None:
        audit = audit_assistance(
            AssistanceDeclared(h=HClass.H2),
            (
                AssistanceImpact(h=HClass.H2, source="canonical_transition"),
                AssistanceImpact(h=HClass.H6, source="stockfish_top_k"),
            ),
        )
        assert audit.violated
        assert audit.effective_h is HClass.H6

    def test_no_violation_when_matching(self) -> None:
        audit = audit_assistance(
            AssistanceDeclared(h=HClass.H3),
            (AssistanceImpact(h=HClass.H3, source="legal_action_set"),),
        )
        assert not audit.violated

    def test_k_axis_independent(self) -> None:
        impacts = (AssistanceImpact(h=HClass.H2, k=KClass.K4, source="engine_derived"),)
        assert effective_assistance(impacts) == (HClass.H2, KClass.K4)


@pytest.mark.unit
class TestEvents:
    def test_envelope_validation(self) -> None:
        envelope = EventEnvelope.create(
            event_type="provider.call.completed",
            payload={"usage": {"input_tokens": 1}},
            stream_type="step",
            stream_id="stp_test1234567890123456",
            sequence=0,
            context=EventContext(run_id="run_test123456789012345"),
        )
        assert envelope.schema_version == "zgw.event/v1alpha1"
        assert envelope.stream.sequence == 0
        line = envelope.to_json_line()
        assert '"event_type":"provider.call.completed"' in line

    def test_bad_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id="evt_x1234567890123456789",
                event_type="Bad Type",
                event_version=1,
                occurred_at=datetime.now(UTC),
                stream=EventStreamRef(type="run", id="run_test123456789012345", sequence=0),
                context=EventContext(run_id="run_test123456789012345"),
                payload={},
            )

    def test_sequence_monotonic_per_stream(self) -> None:
        stream_a = EventStreamRef(type="step", id="s1_1234567890123456789", sequence=0)
        stream_b = EventStreamRef(type="step", id="s1_1234567890123456789", sequence=1)
        assert stream_a.sequence < stream_b.sequence


def _minimal_manifest_data() -> dict:
    return {
        "api_version": "zgw.dev/v1alpha1",
        "kind": "Experiment",
        "metadata": {"name": "unit-test", "tags": ["unit"]},
        "spec": {
            "seed": 1,
            "task": {"plugin": "fake.counter", "config": {"episodes": 1}},
            "players": {
                "white": {
                    "model": {
                        "backend": "fake.backend",
                        "provider": "fake",
                        "model": "scripted",
                        "strategy": "fake.direct",
                    }
                },
                "black": {"policy": {"plugin": "fake.stay"}},
            },
            "protocol": {"declared_assistance": "H2", "declared_knowledge": "K0"},
            "budget": {"max_calls": 10},
            "evaluation": [],
            "artifacts": {"redact": "standard"},
        },
    }


@pytest.mark.unit
class TestManifests:
    def test_minimal_manifest_valid(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        assert manifest.metadata.name == "unit-test"

    def test_extra_field_rejected(self) -> None:
        data = _minimal_manifest_data()
        data["spec"]["surprise"] = 1
        with pytest.raises(ValidationError):
            SourceManifest.model_validate(data)

    def test_bad_name_rejected(self) -> None:
        data = _minimal_manifest_data()
        data["metadata"]["name"] = "Bad Name!"
        with pytest.raises(ValidationError):
            SourceManifest.model_validate(data)

    def test_matrix_product_expansion_deterministic(self) -> None:
        data = _minimal_manifest_data()
        data["spec"]["matrix"] = {
            "mode": "product",
            "parameters": {
                "strategy": ["a", "b"],
                "model": ["x", "y", "z"],
            },
        }
        manifest = SourceManifest.model_validate(data)
        conditions = expand_matrix(manifest.metadata.name, manifest.spec)
        assert len(conditions) == 6
        ids = [c.condition_id for c in conditions]
        assert ids == [c.condition_id for c in expand_matrix(manifest.metadata.name, manifest.spec)]
        assert len(set(ids)) == 6
        pairs = {(c.parameters["strategy"], c.parameters["model"]) for c in conditions}
        assert pairs == {("a", "x"), ("a", "y"), ("a", "z"), ("b", "x"), ("b", "y"), ("b", "z")}

    def test_matrix_zip_requires_equal_lengths(self) -> None:
        data = _minimal_manifest_data()
        data["spec"]["matrix"] = {
            "mode": "zip",
            "parameters": {"a": [1, 2], "b": [1]},
        }
        manifest = SourceManifest.model_validate(data)
        with pytest.raises(ManifestValidationError):
            expand_matrix(manifest.metadata.name, manifest.spec)

    def test_patch_applies_and_validates(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        patched = ManifestPatch(path="/spec/budget/max_calls", value=5).apply(manifest)
        assert patched.spec.budget.max_calls == 5

    def test_patch_missing_path_rejected(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        with pytest.raises(PatchApplicationError):
            ManifestPatch(path="/spec/budget/nope", value=1).apply(manifest)

    def test_patch_invalid_value_rejected(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        with pytest.raises(PatchApplicationError):
            ManifestPatch(path="/spec/budget/max_calls", value="many").apply(manifest)

    def test_resolve_protocol_hash_stable(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        first = resolve_manifest(manifest)
        second = resolve_manifest(SourceManifest.model_validate(_minimal_manifest_data()))
        assert first.protocol_hash == second.protocol_hash
        assert first.conditions[0].condition_id == second.conditions[0].condition_id

    def test_resolved_is_frozen(self) -> None:
        manifest = SourceManifest.model_validate(_minimal_manifest_data())
        resolved = resolve_manifest(manifest)
        with pytest.raises(ValidationError):
            resolved.warnings = ("x",)  # type: ignore[misc]


@pytest.mark.unit
class TestPlayerValidation:
    def test_player_must_choose_model_or_policy(self) -> None:
        data = _minimal_manifest_data()
        data["spec"]["players"]["white"] = {"model": None, "policy": None}
        with pytest.raises(ValidationError):
            SourceManifest.model_validate(data)
