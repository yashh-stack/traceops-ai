"""
Asynchronous OpenTelemetry Span Exporter for TraceOps AI.
Uses BatchSpanProcessor with bounded queue & short export timeout off the critical path,
5-10% nominal + 100% HALT/SUSPEND_HITL sampling, and a bounded deque(maxlen=500) ring buffer.
All payloads are scrubbed for PII/secrets before leaving the container.
"""
from __future__ import annotations

import logging
import threading
import zlib
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Status, StatusCode

from traceops.config import get_settings
from traceops.security import redact_payload, redact_string

logger = logging.getLogger("traceops.otel")


class BoundedRingBufferSpanExporter(SpanExporter):
    """Thread-safe OTel SpanExporter retaining at most `maxlen` spans in memory."""

    def __init__(self, maxlen: int = 500):
        self._buffer: Deque[ReadableSpan] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._shutdown = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._shutdown:
            return SpanExportResult.FAILURE
        with self._lock:
            for span in spans:
                self._buffer.append(span)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._shutdown = True

    def force_flush(self, timeout_millis: int = 1000) -> bool:
        return True

    def get_finished_spans(self) -> List[ReadableSpan]:
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


class TraceOpsOtelEmitter:
    """
    Async-batched OpenTelemetry Span Emitter with tail-biased sampling
    (100% of HALT/SUSPEND_HITL traces, 5-10% of nominal traces) and bounded ring buffer.
    """

    _instance: Optional[TraceOpsOtelEmitter] = None

    def __init__(
        self,
        maxlen: Optional[int] = None,
        max_queue_size: Optional[int] = None,
        export_timeout_millis: Optional[int] = None,
        nominal_sample_rate: Optional[float] = None,
    ):
        settings = get_settings()
        self.maxlen = maxlen if maxlen is not None else settings.otel_ring_buffer_maxlen
        self.max_queue_size = (
            max_queue_size if max_queue_size is not None else settings.otel_queue_size
        )
        self.export_timeout_millis = (
            export_timeout_millis
            if export_timeout_millis is not None
            else settings.otel_export_timeout_ms
        )
        self.nominal_sample_rate = (
            nominal_sample_rate
            if nominal_sample_rate is not None
            else settings.otel_nominal_sample_rate
        )

        self.span_exporter = BoundedRingBufferSpanExporter(maxlen=self.maxlen)
        self.span_processor = BatchSpanProcessor(
            self.span_exporter,
            max_queue_size=self.max_queue_size,
            schedule_delay_millis=200,
            export_timeout_millis=self.export_timeout_millis,
            max_export_batch_size=min(256, self.max_queue_size),
        )
        self.tracer_provider = TracerProvider()
        self.tracer_provider.add_span_processor(self.span_processor)
        self.tracer = self.tracer_provider.get_tracer("traceops.circuit_breaker", "0.2.0")

    @classmethod
    def get_instance(cls) -> TraceOpsOtelEmitter:
        if cls._instance is None:
            cls._instance = TraceOpsOtelEmitter()
        return cls._instance

    def _should_sample(self, trace_id_str: str, decision: str) -> bool:
        """Sample 100% of tripped breakers / HITL; sample nominal traces at configured rate."""
        if decision in ("HALT", "SUSPEND_HITL"):
            return True
        if self.nominal_sample_rate >= 1.0:
            return True
        if self.nominal_sample_rate <= 0.0:
            return False
        bucket = (zlib.crc32(trace_id_str.encode("utf-8")) % 1000) / 1000.0
        return bucket < self.nominal_sample_rate

    def emit_decision_span(
        self,
        trace_id_str: str,
        tool_name: str,
        decision: str,
        mode: str,
        latency_ms: float,
        tier1_status: str,
        drift_score: float,
        reason: str,
        estimated_usd_saved: float,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build redacted span payload and enqueue OTel span asynchronously via BatchSpanProcessor.
        Never blocks the synchronous hot path.
        """
        safe_reason = redact_string(reason)
        span_name = f"traceops.guard.{tool_name}"
        sampled = self._should_sample(trace_id_str, decision)
        safe_args = redact_payload(arguments) if sampled else {}

        if sampled:
            with self.tracer.start_as_current_span(span_name) as span:
                span.set_attribute("traceops.trace_id", trace_id_str)
                span.set_attribute("traceops.tool_name", tool_name)
                span.set_attribute("traceops.decision", decision)
                span.set_attribute("traceops.mode", mode)
                span.set_attribute("traceops.latency_ms", float(latency_ms))
                span.set_attribute("traceops.tier1_status", tier1_status)
                span.set_attribute("traceops.drift_score", float(drift_score))
                span.set_attribute("traceops.reason", safe_reason)
                span.set_attribute("traceops.usd_saved", float(estimated_usd_saved))
                span.set_attribute("traceops.sampled", True)

                if decision == "HALT":
                    span.set_status(Status(StatusCode.ERROR, description=safe_reason))
                else:
                    span.set_status(Status(StatusCode.OK))

        return {
            "name": span_name,
            "trace_id": trace_id_str,
            "tool_name": tool_name,
            "decision": decision,
            "mode": mode,
            "latency_ms": latency_ms,
            "drift_score": drift_score,
            "reason": safe_reason,
            "arguments": safe_args,
            "estimated_usd_saved": estimated_usd_saved,
            "sampled": sampled,
        }

    def get_recent_spans(self, limit: int = 50, flush: bool = True) -> List[Dict[str, Any]]:
        """Fetch spans from bounded ring buffer for dashboard/API inspection."""
        if flush:
            try:
                self.tracer_provider.force_flush(timeout_millis=min(500, self.export_timeout_millis))
            except Exception as exc:
                logger.debug("Span flush skipped: %s", exc)

        all_spans = self.span_exporter.get_finished_spans()
        recent = all_spans[-limit:] if len(all_spans) > limit else all_spans
        formatted: List[Dict[str, Any]] = []
        for s in recent:
            formatted.append(
                {
                    "name": s.name,
                    "attributes": dict(s.attributes) if s.attributes else {},
                    "status": s.status.status_code.name if s.status else "UNSET",
                    "duration_ms": (
                        (s.end_time - s.start_time) / 1_000_000
                        if s.end_time and s.start_time
                        else 0.0
                    ),
                }
            )
        return formatted

    def clear(self) -> None:
        """Flush pending queue and clear bounded memory ring buffer."""
        try:
            self.tracer_provider.force_flush(timeout_millis=200)
        except Exception as exc:
            logger.debug("Span flush during clear skipped: %s", exc)
        self.span_exporter.clear()
