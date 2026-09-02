"""OpenTelemetry wiring.

One call -- ``setup_telemetry(app)`` from ``create_app`` -- installs the tracer and
meter providers, the exporters, and the auto-instrumentation for FastAPI, SQLAlchemy,
httpx (which the OpenAI SDK uses underneath), Elasticsearch, and logging.

Manual spans live where no instrumentation exists: agent nodes (``agents/base.py``),
Neo4j queries (``clients/neo4j.py``), and LLM calls (``clients/llm.py``).
"""

from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_INSTALLED = False

# --- Semantic-convention attribute names used across the codebase ---
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    return metrics.get_meter(name)


def _build_span_processor(settings: Settings) -> Any:
    """Console for local dev, OTLP for anything real."""
    if settings.OTEL_TRACES_EXPORTER == "console":
        return SimpleSpanProcessor(ConsoleSpanExporter())

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    return BatchSpanProcessor(exporter)


def _install_metrics(settings: Settings, resource: Resource) -> None:
    if settings.OTEL_TRACES_EXPORTER != "otlp":
        metrics.set_meter_provider(MeterProvider(resource=resource))
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))


def _instrument_libraries(app: Any) -> None:
    """Auto-instrumentation. Each import is local so a missing optional package
    degrades to a warning instead of breaking startup."""
    from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    ElasticsearchInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=False)


def setup_telemetry(app: Any, settings: Settings) -> None:
    """Idempotent. Honours ``OTEL_SDK_DISABLED`` so tests and CI run with tracing off."""
    global _INSTALLED
    if _INSTALLED or settings.OTEL_SDK_DISABLED:
        logger.info("Telemetry not installed (disabled=%s)", settings.OTEL_SDK_DISABLED)
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    if settings.OTEL_TRACES_EXPORTER != "none":
        provider.add_span_processor(_build_span_processor(settings))
    trace.set_tracer_provider(provider)
    _install_metrics(settings, resource)

    try:
        _instrument_libraries(app)
    except Exception:
        logger.exception("Auto-instrumentation partially failed; manual spans still active")

    _INSTALLED = True
    logger.info(
        "Telemetry installed: service=%s exporter=%s",
        settings.OTEL_SERVICE_NAME,
        settings.OTEL_TRACES_EXPORTER,
    )
