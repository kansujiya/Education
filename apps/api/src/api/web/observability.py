"""Observability bootstrap.

Both OTel and Sentry are **opt-in**: if the relevant env vars are
empty (the test default), the bootstrap is a no-op. Production sets
``OTEL_EXPORTER_OTLP_ENDPOINT`` and / or ``SENTRY_DSN`` and gets traces
+ error reporting wired into the FastAPI app with one call.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from api.config import settings

logger = logging.getLogger(__name__)


def configure_observability(app: FastAPI) -> None:
    _configure_otel(app)
    _configure_sentry()


def _configure_otel(app: FastAPI) -> None:
    if not settings.otel_exporter_otlp_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("opentelemetry packages not installed; skipping OTel.")
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info(
        "OTel configured: endpoint=%s service=%s",
        settings.otel_exporter_otlp_endpoint,
        settings.otel_service_name,
    )


def _configure_sentry() -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry-sdk not installed; skipping Sentry.")
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("Sentry configured.")
