"""Backend caller: a ModelBackend decorator that records every attempt (design §12.9).

Every provider call becomes an attempt row plus started/completed/failed
events. Transport retries create NEW attempts with new IDs. Ambiguous
timeouts are recorded ``outcome_unknown`` and never blindly retried.
"""

from __future__ import annotations

import time
from typing import Any

from zugzwang_core.domain.errors import (
    ProviderTimeoutError,
    ProviderTransportError,
    Retryability,
)
from zugzwang_core.domain.events import EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id
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
    InsertArtifactCommand,
    InsertAttemptCommand,
    PersistenceWriter,
    UpdateAttemptCommand,
)


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
        self._inner = inner
        self._writer = writer
        self._event_sink = event_sink
        self._max_transport_retries = max_transport_retries
        self._attempt_counter: dict[str, int] = {}
        self._artifact_store = artifact_store
        self._capture_requests = capture_raw_requests
        self._capture_responses = capture_raw_responses

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
        key = context.step_id or context.run_id
        ordinal = self._attempt_counter.get(key, 0)
        while True:
            attempt_id = str(new_id("att"))
            attempt_context = context.model_copy(update={"attempt_id": attempt_id})
            started = time.monotonic()
            event_context = EventContext(
                run_id=context.run_id,
                episode_id=context.episode_id,
                step_id=context.step_id,
                attempt_id=attempt_id,
                trace_id=context.trace_id,
            )
            self._writer.enqueue(
                InsertAttemptCommand(
                    row={
                        "attempt_id": attempt_id,
                        "step_id": context.step_id or "",
                        "kind": "provider",
                        "ordinal": ordinal,
                        "status": "started",
                        "outcome_unknown": 0,
                    }
                )
            )
            request_refs: tuple[str, ...] = ()
            if self._capture_requests and self._artifact_store is not None:
                request_refs = (self._capture_request(request, attempt_id),)
            self._emit(
                event_context,
                "provider.call.started",
                {"ordinal": ordinal},
                artifact_refs=request_refs,
            )
            try:
                result = await self._inner.infer(request, attempt_context)
            except ProviderTimeoutError as exc:
                latency = int((time.monotonic() - started) * 1000)
                self._record_outcome(
                    attempt_id, "timeout_unknown", exc.stable_code, latency, unknown=True
                )
                self._emit(
                    event_context,
                    "provider.call.timeout_unknown",
                    {"ordinal": ordinal, "stable_code": exc.stable_code, "latency_ms": latency},
                )
                self._attempt_counter[key] = ordinal + 1
                raise
            except ProviderTransportError as exc:
                latency = int((time.monotonic() - started) * 1000)
                self._record_outcome(attempt_id, "failed", exc.stable_code, latency)
                self._emit(
                    event_context,
                    "provider.call.failed",
                    {"ordinal": ordinal, "stable_code": exc.stable_code, "latency_ms": latency},
                )
                if ordinal < self._max_transport_retries and exc.retryability in (
                    Retryability.TRANSPORT,
                    Retryability.THROTTLING,
                ):
                    ordinal += 1
                    continue
                self._attempt_counter[key] = ordinal + 1
                raise
            except Exception as exc:
                latency = int((time.monotonic() - started) * 1000)
                code = getattr(exc, "stable_code", "ZGZ-PROVIDER_RESPONSE-000")
                self._record_outcome(attempt_id, "failed", code, latency)
                self._emit(
                    event_context,
                    "provider.call.failed",
                    {"ordinal": ordinal, "stable_code": code, "latency_ms": latency},
                )
                self._attempt_counter[key] = ordinal + 1
                raise

            latency = int((time.monotonic() - started) * 1000)
            response = result.response
            self._writer.enqueue(
                UpdateAttemptCommand(
                    attempt_id=attempt_id,
                    values={
                        "status": "completed",
                        "outcome_unknown": 0,
                        "latency_ms": latency,
                        "usage_json": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "source": response.usage.source.value,
                        },
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
            response_refs: tuple[str, ...] = ()
            if self._capture_responses and self._artifact_store is not None:
                response_refs = (self._capture_response(response, attempt_id),)
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
                },
                artifact_refs=response_refs,
            )
            self._attempt_counter[key] = ordinal + 1
            return result

    def _capture_request(self, request: ModelRequest, attempt_id: str) -> str:
        from zugzwang_core.domain.artifacts import ArtifactPayload
        from zugzwang_core.domain.canonical import canonical_json_bytes
        from zugzwang_core.domain.clocks import to_iso_z, utc_now

        data = canonical_json_bytes(request.model_dump(mode="json"))
        ref = self._artifact_store.put(
            ArtifactPayload(media_type="application/vnd.zugzwang.model-request+json", data=data)
        )
        self._writer.enqueue(
            InsertArtifactCommand(
                row={
                    "artifact_id": ref.as_id(),
                    "algorithm": "sha256",
                    "size_bytes": len(data),
                    "media_type": "application/vnd.zugzwang.model-request+json",
                    "relative_path": ref.storage_path(),
                    "created_at": to_iso_z(utc_now()),
                }
            )
        )
        return ref.as_id()

    def _capture_response(self, response: NormalizedResponse, attempt_id: str) -> str:
        from zugzwang_core.domain.artifacts import ArtifactPayload
        from zugzwang_core.domain.canonical import canonical_json_bytes
        from zugzwang_core.domain.clocks import to_iso_z, utc_now

        data = canonical_json_bytes(response.model_dump(mode="json"))
        ref = self._artifact_store.put(
            ArtifactPayload(media_type="application/vnd.zugzwang.model-response+json", data=data)
        )
        self._writer.enqueue(
            InsertArtifactCommand(
                row={
                    "artifact_id": ref.as_id(),
                    "algorithm": "sha256",
                    "size_bytes": len(data),
                    "media_type": "application/vnd.zugzwang.model-response+json",
                    "relative_path": ref.storage_path(),
                    "created_at": to_iso_z(utc_now()),
                }
            )
        )
        return ref.as_id()

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
