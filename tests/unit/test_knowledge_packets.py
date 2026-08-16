"""ZGW-0074: K0-K7 taxonomy, KnowledgePacket contract, resolution and injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zugzwang_core.domain.assistance import KClass
from zugzwang_core.domain.knowledge import (
    KnowledgePacket,
    PacketContent,
    estimate_tokens,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_DIR = REPO_ROOT / "experiments" / "research-suite-0.1"

NAJDORF_FEN = "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6"


def _load(ref: str) -> dict:
    return pytest.importorskip("yaml").safe_load(
        (SUITE_DIR / "knowledge" / f"{ref}.yaml").read_text(encoding="utf-8")
    )


class TestKClassTaxonomy:
    def test_k0_to_k7_defined(self) -> None:
        for name in ("K0", "K1", "K2", "K3", "K4", "K5", "K6", "K7"):
            assert KClass[name].value == int(name[1])

    def test_k8_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            KnowledgePacket.model_validate(
                {
                    "id": "x",
                    "version": "1",
                    "title": "x",
                    "knowledge_class": "K8",
                    "scope": {"domain": "chess"},
                    "content": {"principles": ["p"]},
                    "provenance": {
                        "kind": "t",
                        "curator": "c",
                        "sources": ["s"],
                        "license": "l",
                        "created_at": "2026-08-16T00:00:00Z",
                    },
                }
            )


class TestPacketContract:
    def test_all_suite_packets_validate(self) -> None:
        for path in sorted((SUITE_DIR / "knowledge").glob("*.yaml")):
            raw = pytest.importorskip("yaml").safe_load(path.read_text(encoding="utf-8"))
            packet = KnowledgePacket.model_validate(raw["packet"])
            assert packet.with_content_hash().content_hash

    def test_packets_pass_json_schema(self) -> None:
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(
            (REPO_ROOT / "schemas" / "knowledge-packet.schema.json").read_text(encoding="utf-8")
        )
        for path in sorted((SUITE_DIR / "knowledge").glob("*.yaml")):
            raw = pytest.importorskip("yaml").safe_load(path.read_text(encoding="utf-8"))
            jsonschema.validate(raw, schema)

    def test_content_hash_stable_and_content_sensitive(self) -> None:
        s4 = KnowledgePacket.model_validate(_load("skill-001-s4-najdorf-plans")["packet"])
        a = s4.with_content_hash().content_hash
        b = s4.with_content_hash().content_hash
        assert a == b
        mutated = s4.model_copy(
            update={
                "content": PacketContent(principles=(*s4.content.principles, "extra principle"))
            }
        )
        assert mutated.with_content_hash().content_hash != a

    def test_leakage_audit_flags_engine_markers_below_k7(self) -> None:
        packet = KnowledgePacket.model_validate(_load("skill-001-s4-najdorf-plans")["packet"])
        assert packet.audit_leakage() == ()
        dirty = packet.model_copy(
            update={
                "content": PacketContent(
                    principles=(
                        "The best move is Nf3, cp +35 for White.",
                        *packet.content.principles,
                    )
                )
            }
        )
        assert dirty.audit_leakage()

    def test_s8_k7_allowed_to_carry_engine_language(self) -> None:
        s8 = KnowledgePacket.model_validate(_load("skill-001-s8-engine-verbalized")["packet"])
        assert s8.k_class == KClass.K7
        assert s8.audit_leakage() == ()

    def test_token_matching_across_s4_s5_s6(self) -> None:
        s4 = KnowledgePacket.model_validate(_load("skill-001-s4-najdorf-plans")["packet"])
        s5 = KnowledgePacket.model_validate(_load("skill-001-s5-wrong-plausible")["packet"])
        s6 = KnowledgePacket.model_validate(_load("skill-001-s6-irrelevant")["packet"])
        t4 = estimate_tokens(s4.rendered_body())
        t5 = estimate_tokens(s5.rendered_body())
        t6 = estimate_tokens(s6.rendered_body())
        assert abs(t4 - t5) <= max(4, t4 // 10), (t4, t5)
        assert abs(t4 - t6) <= max(4, t4 // 10), (t4, t6)


class TestResolutionAndInjection:
    def test_load_knowledge_packets_resolves_and_hashes(self) -> None:
        from zugzwang_runtime.application.knowledge import load_knowledge_packets

        packets = load_knowledge_packets(
            SUITE_DIR / "manifest.yaml", ("skill-001-s4-najdorf-plans",)
        )
        assert len(packets) == 1
        assert packets[0].content_hash

    def test_missing_packet_fails_closed(self) -> None:
        from zugzwang_core.domain.errors import ManifestValidationError
        from zugzwang_runtime.application.knowledge import load_knowledge_packets

        with pytest.raises(ManifestValidationError):
            load_knowledge_packets(SUITE_DIR / "manifest.yaml", ("does-not-exist",))

    def test_protocol_hash_changes_with_packet_content(self) -> None:
        from zugzwang_core.domain.manifests import (
            Metadata,
            PlayerModelSpec,
            PlayerPolicySpec,
            PlayerSpec,
            ProtocolSpec,
            SourceManifest,
            Spec,
            TaskSpec,
            resolve_manifest,
        )
        from zugzwang_runtime.application.knowledge import load_knowledge_packets

        s4 = load_knowledge_packets(SUITE_DIR / "manifest.yaml", ("skill-001-s4-najdorf-plans",))
        manifest = SourceManifest(
            metadata=Metadata(name="k-test"),
            spec=Spec(
                seed=1,
                task=TaskSpec(plugin="chess.tasks", config={"kind": "move-selection"}),
                players={
                    "white": PlayerSpec(model=PlayerModelSpec(backend="fake.backend")),
                    "black": PlayerSpec(policy=PlayerPolicySpec(plugin="fake.stay")),
                },
                protocol=ProtocolSpec(
                    declared_assistance="H2",
                    declared_knowledge="K4",
                    knowledge_packets=("skill-001-s4-najdorf-plans",),
                ),
            ),
        )
        a = resolve_manifest(manifest, knowledge_packets=s4).protocol_hash
        mutated = (s4[0].model_copy(update={"version": "1.0.1"}).with_content_hash(),)
        b = resolve_manifest(manifest, knowledge_packets=mutated).protocol_hash
        assert a != b

    def test_strategy_renders_packets_and_records_k_impact(self) -> None:
        from zugzwang_chess.strategies._knowledge import (
            knowledge_impacts,
            render_knowledge_section,
        )

        packets = __import__(
            "zugzwang_runtime.application.knowledge", fromlist=["load_knowledge_packets"]
        ).load_knowledge_packets(
            SUITE_DIR / "manifest.yaml",
            ("skill-001-s4-najdorf-plans", "skill-001-s6-irrelevant"),
        )
        section = render_knowledge_section(packets)
        assert "Najdorf" in section
        assert "K4" in section
        impacts = knowledge_impacts(packets)
        assert {i.k for i in impacts} == {KClass.K4, KClass.K1}
