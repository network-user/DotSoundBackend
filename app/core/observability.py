"""Observability bootstrap: Prometheus, OpenTelemetry, Sentry.

Optional. All exporters initialize only when corresponding settings
are non-empty so dev environments still boot without telemetry.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_metrics_initialized = False
_tracing_initialized = False
_sentry_initialized = False

_PROM_HTTP_REQUESTS = None
_PROM_HTTP_DURATION = None
_PROM_HTTP_ERRORS = None
_PROM_WS_GAUGE = None


def _is_internal_ip(client_host: str | None) -> bool:
    if not client_host:
        return False
    if client_host in {
        "127.0.0.1",
        "::1",
        "localhost",
    }:
        return True
    return bool(client_host.startswith(("10.", "192.168.", "172.")))


def setup_metrics(application: object) -> None:
    """Install Prometheus instrumentation + /metrics endpoint."""
    global _metrics_initialized
    global _PROM_HTTP_REQUESTS
    global _PROM_HTTP_DURATION
    global _PROM_HTTP_ERRORS
    global _PROM_WS_GAUGE
    if _metrics_initialized:
        return
    try:
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            CollectorRegistry,
            Counter,
            Gauge,
            Histogram,
            generate_latest,
        )
    except ImportError:
        logger.warning("prometheus_client_missing")
        return

    registry = CollectorRegistry()
    _PROM_HTTP_REQUESTS = Counter(
        "http_requests_total",
        "Total HTTP requests by method/path/status.",
        ["method", "path", "status"],
        registry=registry,
    )
    _PROM_HTTP_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency by method/path.",
        ["method", "path"],
        registry=registry,
    )
    _PROM_HTTP_ERRORS = Counter(
        "http_errors_total",
        "Total HTTP responses with status >= 500.",
        ["method", "path"],
        registry=registry,
    )
    _PROM_WS_GAUGE = Gauge(
        "active_websocket_connections",
        "Currently open WebSocket connections.",
        registry=registry,
    )

    from fastapi import FastAPI
    from starlette.middleware.base import (
        BaseHTTPMiddleware,
    )
    from starlette.requests import Request
    from starlette.responses import (
        PlainTextResponse,
        Response,
    )

    if not isinstance(application, FastAPI):
        return

    class _MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(
            self,
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            start = time.perf_counter()
            response: Response | None = None
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            finally:
                elapsed = time.perf_counter() - start
                method = request.method.upper()
                route = request.scope.get("route")
                path = (
                    route.path
                    if route is not None and hasattr(route, "path")
                    else request.url.path
                )
                if _PROM_HTTP_REQUESTS is not None:
                    _PROM_HTTP_REQUESTS.labels(
                        method=method,
                        path=path,
                        status=str(status_code),
                    ).inc()
                if _PROM_HTTP_DURATION is not None:
                    _PROM_HTTP_DURATION.labels(
                        method=method, path=path
                    ).observe(elapsed)
                if _PROM_HTTP_ERRORS is not None and status_code >= 500:
                    _PROM_HTTP_ERRORS.labels(method=method, path=path).inc()

    application.add_middleware(_MetricsMiddleware)

    @application.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(
        request: Request,
    ) -> Response:
        client_host = (
            request.client.host if request.client is not None else None
        )
        if not _is_internal_ip(client_host):
            return PlainTextResponse("forbidden", status_code=403)
        body = generate_latest(registry)
        return PlainTextResponse(
            content=body.decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    _metrics_initialized = True
    logger.info("observability_metrics_ready")


def setup_tracing() -> None:
    global _tracing_initialized
    if _tracing_initialized:
        return
    from app.config import settings

    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: E501
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import (
            Resource,
        )
        from opentelemetry.sdk.trace import (
            TracerProvider,
        )
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
        )
    except ImportError:
        logger.warning("opentelemetry_missing")
        return

    resource = Resource.create({"service.name": "dotsound-backend"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.fastapi import (  # noqa: E501
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor().instrument()
    except Exception:
        logger.exception("otel_fastapi_instrument_failed")

    try:
        from opentelemetry.instrumentation.sqlalchemy import (  # noqa: E501
            SQLAlchemyInstrumentor,
        )

        SQLAlchemyInstrumentor().instrument()
    except Exception:
        logger.exception("otel_sqlalchemy_instrument_failed")

    _tracing_initialized = True
    logger.info("observability_tracing_ready")


def _sentry_pii_filter(
    event: dict[str, object], _hint: dict[str, object]
) -> dict[str, object] | None:
    from dotsound_private_core.services.admin_security_policy import (
        ADMIN_PII_KEYS,
    )

    def _scrub(value: object) -> object:
        if isinstance(value, dict):
            return {
                k: ("[REDACTED]" if k.lower() in ADMIN_PII_KEYS else _scrub(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [_scrub(v) for v in value]
        return value

    scrubbed = _scrub(event)
    if isinstance(scrubbed, dict):
        return scrubbed
    return event


def setup_sentry() -> None:
    global _sentry_initialized
    if _sentry_initialized:
        return
    from app.config import settings

    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import (
            FastApiIntegration,
        )
        from sentry_sdk.integrations.starlette import (
            StarletteIntegration,
        )
    except ImportError:
        logger.warning("sentry_sdk_missing")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=(settings.sentry_environment),
        traces_sample_rate=(settings.sentry_traces_sample_rate),
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
        before_send=_sentry_pii_filter,
    )
    _sentry_initialized = True
    logger.info("observability_sentry_ready")


def setup_observability(
    application: object,
) -> None:
    setup_sentry()
    setup_metrics(application)
    setup_tracing()


def ws_gauge_inc() -> None:
    if _PROM_WS_GAUGE is not None:
        _PROM_WS_GAUGE.inc()


def ws_gauge_dec() -> None:
    if _PROM_WS_GAUGE is not None:
        _PROM_WS_GAUGE.dec()
