from __future__ import annotations
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os, json, pathlib, time

class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: str = '.imu_runs/otel_spans.jsonl'):
        self.p = pathlib.Path(path)
        self.p.parent.mkdir(parents=True, exist_ok=True)
    def export(self, spans):
        with self.p.open('a', encoding='utf-8') as f:
            for s in spans:
                ctx = s.get_span_context()
                attrs = getattr(s, 'attributes', {}) or {}
                rec = {
                    'ts': time.time(),
                    'trace_id': str(ctx.trace_id),
                    'span_id': str(ctx.span_id),
                    'name': s.name,
                    'status': str(getattr(getattr(s, 'status', None), 'status_code', 'OK')),
                    'start': getattr(s, 'start_time', 0),
                    'end': getattr(s, 'end_time', 0),
                    'attrs': {k:str(v) for k,v in attrs.items()},
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS


def instrument_app(app: FastAPI, service_name: str = 'imu-api') -> None:
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '')
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    # JSONL תמיד נשאר
    provider.add_span_processor(BatchSpanProcessor(JsonlSpanExporter()))

    # OTLP רק אם באמת הוגדר
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
