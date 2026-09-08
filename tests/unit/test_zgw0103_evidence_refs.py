"""ZGW-0103 R1 — CallRecord↔response joins by call identity, never by order.

Regression for the corpus dossier §13 finding: 2.068/2.273 trace references
mismatched because the trace stitcher fell back to a reversed walk over the
attempt evidence when the synthetic call id missed. Evidence unknown must stay
absent; two calls with distinct usage must each keep their OWN response.
"""

import pytest

from zugzwang_core.domain.money import TokenUsage
from zugzwang_core.ports.strategy import CallRecord, DecisionTrace
from zugzwang_runtime.execution.evidence import decision_trace_payload

pytestmark = pytest.mark.unit


def _trace(calls: list[CallRecord]) -> DecisionTrace:
    return DecisionTrace(
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0",
        declared_regime="R7",
        calls=tuple(calls),
    )


def _call(attempt_id: str) -> CallRecord:
    return CallRecord(
        attempt_id=attempt_id,
        request_fingerprint="fp",
        response_ok=True,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )


def test_two_calls_keep_their_own_response_refs() -> None:
    trace = _trace([_call("c1"), _call("c2")])
    payload = decision_trace_payload(
        run_id="run-1",
        episode_id="ep-1",
        step_id="st-1",
        trace=trace,
        attempt_index=0,
        attempt_evidence={
            "c1": {
                "request_artifact_ref": None,
                "wire_request_artifact_ref": "art:wire-req-1",
                "wire_response_artifact_ref": "art:wire-resp-1",
                "response_artifact_ref": "art:resp-1",
                "reasoning_telemetry_artifact_ref": None,
            },
            "c2": {
                "request_artifact_ref": None,
                "wire_request_artifact_ref": "art:wire-req-2",
                "wire_response_artifact_ref": "art:wire-resp-2",
                "response_artifact_ref": "art:resp-2",
                "reasoning_telemetry_artifact_ref": None,
            },
        },
    )
    rows = payload["calls"]
    assert rows[0]["response_artifact_ref"] == "art:resp-1"
    assert rows[0]["wire_request_artifact_ref"] == "art:wire-req-1"
    assert rows[1]["response_artifact_ref"] == "art:resp-2"
    assert rows[1]["wire_request_artifact_ref"] == "art:wire-req-2"
    assert payload["artifact_refs"] == [
        "art:resp-1",
        "art:resp-2",
        "art:wire-req-1",
        "art:wire-req-2",
        "art:wire-resp-1",
        "art:wire-resp-2",
    ]


def test_unknown_call_keeps_no_refs_instead_of_stealing_another_response() -> None:
    """The old reversed fallback attached SOME other call's artifacts here —
    the exact mechanism behind the 91% reference mismatch in the dossier."""
    trace = _trace([_call("ghost")])
    payload = decision_trace_payload(
        run_id="run-1",
        episode_id="ep-1",
        step_id="st-1",
        trace=trace,
        attempt_index=0,
        attempt_evidence={
            "real": {"response_artifact_ref": "art:resp-real"},
        },
    )
    row = payload["calls"][0]
    assert row["response_artifact_ref"] is None, "evidence unknown stays unknown"
    assert payload["artifact_refs"] == []
