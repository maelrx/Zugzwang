"""Backend caller: a ModelBackend decorator that records every attempt (design §12.9).

Every provider call becomes an attempt row plus started/completed/failed
events. Transport retries create NEW attempts with new IDs. Ambiguous
timeouts are recorded ``outcome_unknown`` and never blindly retried.
"""

from __future__ import annotations

import time
from typing import Any, cast

from zugzwang_core.domain.errors import (
    ProviderTimeoutError,
    ProviderTransportError,
    Retryability,
)
from zugzwang_core.domain.events import EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id
from zugzwang_core.domain.provider_isolation import ProviderIsolationError, reject_native_execution
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ModelBackend,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
)

from ..persistence.event_sink import PersistentEventSink
from ..persistence.writer import (
    InsertAttemptCommand,
    PersistenceWriter,
    UpdateAttemptCommand,
)
from .evidence import sanitize_wire_payload, store_json_artifact


class RecordingBackend:
    """Wraps a ModelBackend with attempt recording and transport retries.

    Implements the ModelBackend port so strategies use it transparently.
    """

    def __init__(
        self,
        inner: ModelBackend,
        *,
        writer: PersistenceWriter,
        event_sink: PersistentEventSink,
        max_transport_retries: int = 0,
        artifact_store: Any = None,
        capture_raw_requests: bool = False,
        capture_raw_responses: bool = False,
    ) -> None:
        self._isolation_error: ProviderIsolationError | None = None
        self._inner = inner
        self._writer = writer
        self._event_sink = event_sink
        self._max_transport_retries = max_transport_retries
        self._attempt_counter: dict[str, int] = {}
        self._artifact_store = artifact_store
        self._capture_requests = capture_raw_requests
        self._capture_responses = capture_raw_responses
        self._evidence_by_attempt: dict[str, dict[str, str | None]] = {}
        self._decision_attempt_ids: list[str] = []
        # ZGW-0103 R1: caller-supplied attempt id (CallContext.attempt_id) ->
        # merged evidence refs of every real attempt fired under it. Strategies
        # stamp CallRecord.attempt_id with the caller id they chose; joining
        # trace rows to their own response MUST use this identity, never a
        # positional fallback.
        self._caller_evidence: dict[str, dict[str, str | None]] = {}
        # Operator directive 2026-09-08: the last decision's own reasoning
        # summary, replayed as self-memory between moves (manifest-gated).
        self.last_reasoning_summary: str | None = None

    def assert_isolated(self) -> None:
        """A strategy cannot swallow a security failure and commit a fallback."""
        if self._isolation_error is not None:
            raise self._isolation_error

    def begin_decision(self) -> None:
        """Start a local correlation window for one strategy decision."""
        self._decision_attempt_ids = []
        self._caller_evidence = {}

    def evidence_for_attempt(self, attempt_id: str) -> dict[str, str | None]:
        return dict(self._evidence_by_attempt.get(attempt_id, {}))

    def evidence_for_attempts(self) -> dict[str, dict[str, str | None]]:
        return {attempt_id: dict(refs) for attempt_id, refs in self._evidence_by_attempt.items()}

    def evidence_for_current_decision(self) -> dict[str, dict[str, str | None]]:
        return {
            attempt_id: dict(self._evidence_by_attempt[attempt_id])
            for attempt_id in self._decision_attempt_ids
            if attempt_id in self._evidence_by_attempt
        }

    def evidence_for_calls(self) -> dict[str, dict[str, str | None]]:
        """Evidence keyed by the CALLER's attempt id (CallContext.attempt_id).

        This is the join key strategies actually put in ``CallRecord.attempt_id``
        (ZGW-0103 R1). Transport retries under one caller id merge into one
        entry: later attempts overwrite only the fields they really observed,
        so an unknown field from the first try is never fabricated.
        """
        return {caller_id: dict(refs) for caller_id, refs in self._caller_evidence.items()}

    def _merge_caller_evidence(self, caller_id: str, refs: dict[str, str | None]) -> None:
        entry = self._caller_evidence.setdefault(caller_id, {})
        for field, ref in refs.items():
            if ref is not None or field not in entry:
                entry[field] = ref

    @property
    def descriptor(self) -> BackendDescriptor:
        return self._inner.descriptor

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        return await self._inner.inspect_capabilities(model, required, preferred, on_unsupported)

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        self.assert_isolated()
        if request.required_capabilities:
            report = await self._inner.inspect_capabilities(
                request.model,
                required=request.required_capabilities,
                preferred=request.preferred_capabilities,
            )
            if not report.satisfied:
                from zugzwang_core.domain.errors import CapabilityMissingError

                missing = ", ".join(sorted(str(c) for c in report.missing_required))
                raise CapabilityMissingError(
                    f"backend {self._inner.descriptor.backend_id} lacks required capabilities: {missing}"
                )
        key = context.step_id or context.run_id
        ordinal = self._attempt_counter.get(key, 0)
        while True:
            attempt_id = str(new_id("att"))
            caller_id = context.attempt_id or attempt_id
            self._decision_attempt_ids.append(attempt_id)
            attempt_context = context.model_copy(update={"attempt_id": attempt_id})
            started = time.monotonic()
            event_context = EventContext(
                run_id=context.run_id,
                episode_id=context.episode_id,
                step_id=context.step_id,
                attempt_id=attempt_id,
                trace_id=context.trace_id,
            )
            request_ref: str | None = None
            if self._capture_requests and self._artifact_store is not None:
                request_ref = self._capture_request(request)
            self._evidence_by_attempt[attempt_id] = {
                "request_artifact_ref": request_ref,
                "wire_request_artifact_ref": None,
                "wire_response_artifact_ref": None,
                "response_artifact_ref": None,
                "reasoning_telemetry_artifact_ref": None,
            }
            self._writer.enqueue(
                InsertAttemptCommand(
                    row={
                        "attempt_id": attempt_id,
                        "step_id": context.step_id or "",
                        "kind": "provider",
                        "ordinal": ordinal,
                        "status": "started",
                        "outcome_unknown": 0,
                        "request_artifact_id": request_ref,
                    }
                )
            )
            request_refs: tuple[str, ...] = (request_ref,) if request_ref else ()
            self._emit(
                event_context,
                "provider.call.started",
                {"ordinal": ordinal},
                artifact_refs=request_refs,
            )
            try:
                result = await self._inner.infer(request, attempt_context)
                reject_native_execution(result.wire_response)
            except ProviderTimeoutError as exc:
                failed_wire_ref = self._capture_failed_wire_request(attempt_id)
                failed_response_ref = self._capture_failed_wire_response(attempt_id)
                latency = int((time.monotonic() - started) * 1000)
                self._record_outcome(
                    attempt_id, "timeout_unknown", exc.stable_code, latency, unknown=True
                )
                self._merge_caller_evidence(
                    caller_id,
                    {
                        "request_artifact_ref": request_ref,
                        "wire_request_artifact_ref": failed_wire_ref,
                        "wire_response_artifact_ref": failed_response_ref,
                        "response_artifact_ref": None,
                        "reasoning_telemetry_artifact_ref": None,
                    },
                )
                self._emit(
                    event_context,
                    "provider.call.timeout_unknown",
                    {"ordinal": ordinal, "stable_code": exc.stable_code, "latency_ms": latency},
                    artifact_refs=tuple(
                        ref for ref in (failed_wire_ref, failed_response_ref) if ref
                    ),
                )
                self._attempt_counter[key] = ordinal + 1
                raise
            except ProviderTransportError as exc:
                failed_wire_ref = self._capture_failed_wire_request(attempt_id)
                failed_response_ref = self._capture_failed_wire_response(attempt_id)
                latency = int((time.monotonic() - started) * 1000)
                self._record_outcome(attempt_id, "failed", exc.stable_code, latency)
                self._merge_caller_evidence(
                    caller_id,
                    {
                        "request_artifact_ref": request_ref,
                        "wire_request_artifact_ref": failed_wire_ref,
                        "wire_response_artifact_ref": failed_response_ref,
                        "response_artifact_ref": None,
                        "reasoning_telemetry_artifact_ref": None,
                    },
                )
                self._emit(
                    event_context,
                    "provider.call.failed",
                    {"ordinal": ordinal, "stable_code": exc.stable_code, "latency_ms": latency},
                    artifact_refs=tuple(
                        ref for ref in (failed_wire_ref, failed_response_ref) if ref
                    ),
                )
                if ordinal < self._max_transport_retries and exc.retryability in (
                    Retryability.TRANSPORT,
                    Retryability.THROTTLING,
                ):
                    retry_after = getattr(exc, "retry_after", None)
                    if retry_after is not None:
                        # ZGW-0103 R5: a throttling retry honors the provider's
                        # own pacing hint, bounded so a hostile header cannot
                        # stall a campaign slot.
                        time.sleep(min(float(retry_after), 120.0))
                    elif exc.retryability is Retryability.THROTTLING:
                        # No hint advertised (the opencode router's case):
                        # exponential pacing instead of hammering the quota
                        # back-to-back — instant triple-429 killed the first
                        # cb2 launch wave (campaign 2026-09-08).
                        time.sleep(min(2.0 * (2**ordinal), 30.0))
                    ordinal += 1
                    continue
                self._attempt_counter[key] = ordinal + 1
                raise
            except Exception as exc:
                if isinstance(exc, ProviderIsolationError):
                    self._isolation_error = exc
                failed_wire_ref = self._capture_failed_wire_request(attempt_id)
                failed_response_ref = self._capture_failed_wire_response(
                    attempt_id, fallback=getattr(exc, "wire_response", None)
                )
                latency = int((time.monotonic() - started) * 1000)
                code = getattr(exc, "stable_code", "ZGZ-PROVIDER_RESPONSE-000")
                self._record_outcome(attempt_id, "failed", code, latency)
                self._merge_caller_evidence(
                    caller_id,
                    {
                        "request_artifact_ref": request_ref,
                        "wire_request_artifact_ref": failed_wire_ref,
                        "wire_response_artifact_ref": failed_response_ref,
                        "response_artifact_ref": None,
                        "reasoning_telemetry_artifact_ref": None,
                    },
                )
                self._emit(
                    event_context,
                    "provider.call.failed",
                    {"ordinal": ordinal, "stable_code": code, "latency_ms": latency},
                    artifact_refs=tuple(
                        ref for ref in (failed_wire_ref, failed_response_ref) if ref
                    ),
                )
                self._attempt_counter[key] = ordinal + 1
                raise

            latency = int((time.monotonic() - started) * 1000)
            response = result.response
            normalized_ref: str | None = None
            wire_request_ref: str | None = None
            wire_response_ref: str | None = None
            reasoning_ref: str | None = None
            evidence_refs: list[str] = []
            if self._capture_responses and self._artifact_store is not None:
                normalized_ref = self._capture_response(response)
                evidence_refs.append(normalized_ref)
                if result.wire_request is not None:
                    wire_request_ref = self._capture_json(
                        sanitize_wire_payload(result.wire_request),
                        "application/vnd.zugzwang.wire-request+json",
                    )
                    evidence_refs.append(wire_request_ref)
                if result.wire_response is not None:
                    wire_response_ref = self._capture_json(
                        sanitize_wire_payload(result.wire_response),
                        "application/vnd.zugzwang.wire-response+json",
                    )
                    evidence_refs.append(wire_response_ref)
                if result.reasoning_telemetry is not None:
                    self.last_reasoning_summary = result.reasoning_telemetry.reasoning_summary
                    reasoning_ref = self._capture_json(
                        result.reasoning_telemetry.model_dump(mode="json"),
                        "application/vnd.zugzwang.reasoning-telemetry+json",
                    )
                    evidence_refs.append(reasoning_ref)
            self._evidence_by_attempt[attempt_id] = {
                "request_artifact_ref": request_ref,
                "wire_request_artifact_ref": wire_request_ref,
                "wire_response_artifact_ref": wire_response_ref,
                "response_artifact_ref": normalized_ref,
                "reasoning_telemetry_artifact_ref": reasoning_ref,
            }
            self._merge_caller_evidence(
                caller_id,
                self._evidence_by_attempt[attempt_id],
            )
            usage_json: dict[str, Any] = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "source": response.usage.source.value,
            }
            if result.reasoning_telemetry is not None:
                usage_json["reasoning_tokens"] = result.reasoning_telemetry.reasoning_tokens
                usage_json["provider_usage"] = result.reasoning_telemetry.usage
            self._writer.enqueue(
                UpdateAttemptCommand(
                    attempt_id=attempt_id,
                    values={
                        "status": "completed",
                        "outcome_unknown": 0,
                        "latency_ms": latency,
                        "usage_json": usage_json,
                        "request_artifact_id": request_ref,
                        "wire_request_artifact_id": wire_request_ref,
                        "wire_response_artifact_id": wire_response_ref,
                        "response_artifact_id": normalized_ref,
                        "reasoning_telemetry_artifact_id": reasoning_ref,
                        "cost_json": (
                            {
                                "amount": str(response.cost.amount.amount),
                                "status": response.cost.status.value,
                            }
                            if response.cost is not None and response.cost.amount is not None
                            else None
                        ),
                    },
                )
            )
            response_refs: tuple[str, ...] = tuple(evidence_refs)
            self._emit(
                event_context,
                "provider.call.completed",
                {
                    "ordinal": ordinal,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "source": response.usage.source.value,
                    },
                    "latency_ms": latency,
                    "wire_fidelity": response.wire_fidelity.value,
                    "provider_wire_fidelity": result.wire_fidelity.value,
                },
                artifact_refs=response_refs,
            )
            self._attempt_counter[key] = ordinal + 1
            return result

    def _capture_request(self, request: ModelRequest) -> str:
        return store_json_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=request.model_dump(mode="json"),
            media_type="application/vnd.zugzwang.model-request+json",
            redaction_policy="standard",
        ).as_id()

    def _capture_response(self, response: NormalizedResponse) -> str:
        return store_json_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=response.model_dump(mode="json"),
            media_type="application/vnd.zugzwang.model-response+json",
            redaction_policy="standard",
        ).as_id()

    def _capture_json(self, payload: Any, media_type: str) -> str:
        return store_json_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=payload,
            media_type=media_type,
            redaction_policy="standard",
        ).as_id()

    def _capture_failed_wire_request(self, attempt_id: str) -> str | None:
        if not (self._capture_requests or self._capture_responses) or self._artifact_store is None:
            return None
        payload = getattr(self._inner, "_last_wire_request", None)
        if not isinstance(payload, dict):
            return None
        ref = self._capture_json(
            sanitize_wire_payload(payload),
            "application/vnd.zugzwang.wire-request+json",
        )
        refs = self._evidence_by_attempt.setdefault(attempt_id, {})
        refs["wire_request_artifact_ref"] = ref
        self._writer.enqueue(
            UpdateAttemptCommand(
                attempt_id=attempt_id,
                values={"wire_request_artifact_id": ref},
            )
        )
        return ref

    def _capture_failed_wire_response(self, attempt_id: str, fallback: Any = None) -> str | None:
        if not self._capture_responses or self._artifact_store is None:
            return None
        payload = (
            cast("dict[str, Any]", fallback)
            if isinstance(fallback, dict)
            else getattr(self._inner, "_last_wire_response", None)
        )
        if not isinstance(payload, dict):
            return None
        ref = self._capture_json(
            sanitize_wire_payload(payload),
            "application/vnd.zugzwang.wire-response+json",
        )
        refs = self._evidence_by_attempt.setdefault(attempt_id, {})
        refs["wire_response_artifact_ref"] = ref
        self._writer.enqueue(
            UpdateAttemptCommand(
                attempt_id=attempt_id,
                values={"wire_response_artifact_id": ref},
            )
        )
        return ref

    def _record_outcome(
        self,
        attempt_id: str,
        status: str,
        failure_code: str,
        latency_ms: int,
        *,
        unknown: bool = False,
    ) -> None:
        self._writer.enqueue(
            UpdateAttemptCommand(
                attempt_id=attempt_id,
                values={
                    "status": status,
                    "failure_code": failure_code,
                    "outcome_unknown": 1 if unknown else 0,
                    "latency_ms": latency_ms,
                },
            )
        )

    def _emit(
        self,
        context: EventContext,
        event_type: str,
        payload: dict[str, Any],
        artifact_refs: tuple[str, ...] = (),
    ) -> None:
        stream_id = context.step_id or context.run_id
        stream_type = "step" if context.step_id else "run"
        self._event_sink.append(
            EventEnvelope.create(
                event_type=event_type,
                payload=payload,
                stream_type=stream_type,
                stream_id=stream_id,
                sequence=0,
                context=context,
                artifact_refs=artifact_refs,
            )
        )
