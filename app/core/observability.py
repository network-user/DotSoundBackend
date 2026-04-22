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

_PROM_LYRICS_JOBS_TOTAL = None
_PROM_LYRICS_JOB_DURATION = None
_PROM_WORKER_HEARTBEAT_LAG = None
_PROM_WORKER_JOBS_IN_FLIGHT = None
_PROM_SPEECHKIT_SPENT = None
_PROM_SPEECHKIT_BUDGET_REMAINING = None
_PROM_TIER_FALLBACK_TOTAL = None
_PROM_HMAC_AUTH_FAILURES = None
_PROM_WORKER_ANOMALY_TOTAL = None


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

    global _PROM_LYRICS_JOBS_TOTAL
    global _PROM_LYRICS_JOB_DURATION
    global _PROM_WORKER_HEARTBEAT_LAG
    global _PROM_WORKER_JOBS_IN_FLIGHT
    global _PROM_SPEECHKIT_SPENT
    global _PROM_SPEECHKIT_BUDGET_REMAINING
    global _PROM_TIER_FALLBACK_TOTAL
    global _PROM_HMAC_AUTH_FAILURES
    global _PROM_WORKER_ANOMALY_TOTAL

    _PROM_LYRICS_JOBS_TOTAL = Counter(
        "lyrics_jobs_total",
        "Total LyricsJob outcomes by tier and status.",
        ["tier", "status"],
        registry=registry,
    )
    _PROM_LYRICS_JOB_DURATION = Histogram(
        "lyrics_job_duration_seconds",
        "End-to-end LyricsJob duration by tier.",
        ["tier"],
        buckets=(
            1, 5, 15, 30, 60, 120, 300, 600,
        ),
        registry=registry,
    )
    _PROM_WORKER_HEARTBEAT_LAG = Gauge(
        "worker_heartbeat_lag_seconds",
        "Seconds since last heartbeat per worker.",
        ["worker_id"],
        registry=registry,
    )
    _PROM_WORKER_JOBS_IN_FLIGHT = Gauge(
        "worker_jobs_in_flight",
        "Number of running jobs per worker.",
        ["worker_id"],
        registry=registry,
    )
    _PROM_SPEECHKIT_SPENT = Counter(
        "speechkit_spent_rub_total",
        "Cumulative SpeechKit spend in roubles.",
        registry=registry,
    )
    _PROM_SPEECHKIT_BUDGET_REMAINING = Gauge(
        "speechkit_budget_remaining_rub",
        "Roubles left in the current month's budget.",
        registry=registry,
    )
    _PROM_TIER_FALLBACK_TOTAL = Counter(
        "tier_fallback_total",
        "Cascade tier transitions, by from/to/reason.",
        ["from_tier", "to_tier", "reason"],
        registry=registry,
    )
    _PROM_HMAC_AUTH_FAILURES = Counter(
        "hmac_auth_failures_total",
        "Worker HMAC verification failures, by reason.",
        ["reason"],
        registry=registry,
    )
    _PROM_WORKER_ANOMALY_TOTAL = Counter(
        "worker_anomaly_total",
        "Anomaly detector flags raised per type.",
        ["anomaly_type"],
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


def lyrics_job_observed(
    *, tier: str, status: str, duration_seconds: float
) -> None:
    if _PROM_LYRICS_JOBS_TOTAL is not None:
        _PROM_LYRICS_JOBS_TOTAL.labels(
            tier=tier, status=status
        ).inc()
    if _PROM_LYRICS_JOB_DURATION is not None:
        _PROM_LYRICS_JOB_DURATION.labels(
            tier=tier
        ).observe(max(0.0, duration_seconds))


def tier_fallback_observed(
    *, from_tier: str, to_tier: str, reason: str
) -> None:
    if _PROM_TIER_FALLBACK_TOTAL is not None:
        _PROM_TIER_FALLBACK_TOTAL.labels(
            from_tier=from_tier,
            to_tier=to_tier,
            reason=reason,
        ).inc()


def hmac_auth_failure_observed(*, reason: str) -> None:
    if _PROM_HMAC_AUTH_FAILURES is not None:
        _PROM_HMAC_AUTH_FAILURES.labels(
            reason=reason
        ).inc()


def worker_anomaly_observed(*, anomaly_type: str) -> None:
    if _PROM_WORKER_ANOMALY_TOTAL is not None:
        _PROM_WORKER_ANOMALY_TOTAL.labels(
            anomaly_type=anomaly_type
        ).inc()


def worker_heartbeat_lag_observed(
    *, worker_id: str, lag_seconds: float
) -> None:
    if _PROM_WORKER_HEARTBEAT_LAG is not None:
        _PROM_WORKER_HEARTBEAT_LAG.labels(
            worker_id=worker_id
        ).set(max(0.0, lag_seconds))


def worker_jobs_in_flight_set(
    *, worker_id: str, count: int
) -> None:
    if _PROM_WORKER_JOBS_IN_FLIGHT is not None:
        _PROM_WORKER_JOBS_IN_FLIGHT.labels(
            worker_id=worker_id
        ).set(int(count))


def speechkit_spent_inc(rub: float) -> None:
    if _PROM_SPEECHKIT_SPENT is not None:
        _PROM_SPEECHKIT_SPENT.inc(max(0.0, float(rub)))


def speechkit_budget_remaining_set(rub: float) -> None:
    if _PROM_SPEECHKIT_BUDGET_REMAINING is not None:
        _PROM_SPEECHKIT_BUDGET_REMAINING.set(
            max(0.0, float(rub))
        )
