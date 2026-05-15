"""Observability bootstrap: Prometheus, OpenTelemetry, Sentry.

Optional. All exporters initialize only when corresponding settings
are non-empty so dev environments still boot without telemetry.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import cast

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
_PROM_ELASTICSEARCH_QUERIES = None
_PROM_RADIO_REQUESTS = None
_PROM_RADIO_GUARD_HITS = None
_PROM_RADIO_QUEUE_SIZE = None
_PROM_RECSYS_LISTEN_OUTCOMES = None
_PROM_RECSYS_SAVE_ACTIONS = None
_PROM_RECSYS_PIPELINE_LATENCY = None
_PROM_RECSYS_IMPRESSION_POSITION = None
_PROM_OFFLINE_ELIGIBILITY = None
_PROM_OFFLINE_PREFETCH = None
_PROM_CLIENT_PLAYBACK_EVENTS = None

_PROM_TOR_CIRCUIT_FAILURE_RATE = None
_PROM_OUTBOUND_PROXY_POOL_SIZE = None

_PROM_REGISTRY: object | None = None


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


def _metrics_route_present(application: object) -> bool:
    from fastapi import FastAPI

    if not isinstance(application, FastAPI):
        return False
    stack: list[object] = list(application.routes)
    while stack:
        route = stack.pop()
        if getattr(route, "path", None) == "/metrics":
            return True
        nested = getattr(route, "routes", None)
        if nested:
            stack.extend(nested)
    return False


def _attach_prometheus_metrics_route(
    application: object,
    registry: object,
) -> None:
    from fastapi import FastAPI
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        generate_latest,
    )
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse, Response

    if not isinstance(application, FastAPI):
        return
    if _metrics_route_present(application):
        return

    @application.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(
        request: Request,
    ) -> Response:
        client_host = (
            request.client.host if request.client is not None else None
        )
        if not _is_internal_ip(client_host):
            return PlainTextResponse("forbidden", status_code=403)
        body = generate_latest(cast(CollectorRegistry, registry))
        return PlainTextResponse(
            content=body.decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )


def setup_metrics(application: object) -> None:
    """Install Prometheus instrumentation + /metrics endpoint."""
    global _metrics_initialized
    global _PROM_REGISTRY
    global _PROM_HTTP_REQUESTS
    global _PROM_HTTP_DURATION
    global _PROM_HTTP_ERRORS
    global _PROM_WS_GAUGE
    if _metrics_initialized:
        from fastapi import FastAPI

        if isinstance(application, FastAPI) and _PROM_REGISTRY is not None:
            _attach_prometheus_metrics_route(application, _PROM_REGISTRY)
        return
    try:
        from prometheus_client import (
            CollectorRegistry,
            Counter,
            Gauge,
            Histogram,
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
    global _PROM_ELASTICSEARCH_QUERIES
    global _PROM_RADIO_REQUESTS
    global _PROM_RADIO_GUARD_HITS
    global _PROM_RADIO_QUEUE_SIZE

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
            1,
            5,
            15,
            30,
            60,
            120,
            300,
            600,
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
    _PROM_ELASTICSEARCH_QUERIES = Counter(
        "elasticsearch_query_total",
        "Elasticsearch read paths (search/suggest) by outcome.",
        ["op", "outcome"],
        registry=registry,
    )
    _PROM_RADIO_REQUESTS = Counter(
        "radio_requests_total",
        "Radio queue requests by surface and outcome.",
        ["surface", "outcome"],
        registry=registry,
    )
    _PROM_RADIO_GUARD_HITS = Counter(
        "radio_guard_hits_total",
        "Rate-limiter guard hits in radio flows.",
        ["surface"],
        registry=registry,
    )
    _PROM_RADIO_QUEUE_SIZE = Histogram(
        "radio_queue_size",
        "Returned radio queue size per request.",
        ["surface"],
        buckets=(0, 1, 3, 5, 10, 20, 30, 50),
        registry=registry,
    )
    global _PROM_RECSYS_LISTEN_OUTCOMES
    global _PROM_RECSYS_SAVE_ACTIONS
    global _PROM_RECSYS_PIPELINE_LATENCY
    global _PROM_RECSYS_IMPRESSION_POSITION
    _PROM_RECSYS_LISTEN_OUTCOMES = Counter(
        "recsys_listen_outcomes_total",
        (
            "Listen outcomes for tracks shown by recsys, per "
            "surface (completed/skipped_quick/skipped/partial)."
        ),
        ["surface", "outcome"],
        registry=registry,
    )
    _PROM_RECSYS_SAVE_ACTIONS = Counter(
        "recsys_save_actions_total",
        (
            "Post-impression actions (like/playlist_add/dislike) "
            "attributed back to a recsys surface."
        ),
        ["surface", "action"],
        registry=registry,
    )
    _PROM_RECSYS_PIPELINE_LATENCY = Histogram(
        "recsys_pipeline_seconds",
        (
            "Time spent in recsys pipeline stages "
            "(retrieval/ranking/rerank/total)."
        ),
        ["surface", "stage"],
        buckets=(
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
        ),
        registry=registry,
    )
    _PROM_RECSYS_IMPRESSION_POSITION = Histogram(
        "recsys_listen_position",
        (
            "Rank position (1-based) of tracks that resulted in "
            "a qualified listen, per surface."
        ),
        ["surface"],
        buckets=(1, 2, 3, 5, 8, 13, 21, 34, 55, 89),
        registry=registry,
    )

    global _PROM_TOR_CIRCUIT_FAILURE_RATE
    global _PROM_OUTBOUND_PROXY_POOL_SIZE
    _PROM_TOR_CIRCUIT_FAILURE_RATE = Gauge(
        "tor_circuit_failure_rate",
        "Current rolling failure rate for each Tor circuit (0.0–1.0).",
        ["circuit"],
        registry=registry,
    )
    _PROM_OUTBOUND_PROXY_POOL_SIZE = Gauge(
        "outbound_proxy_pool_size",
        "Number of outbound proxy entries active (Tor circuits or static).",
        registry=registry,
    )

    global _PROM_OFFLINE_ELIGIBILITY
    global _PROM_OFFLINE_PREFETCH
    global _PROM_CLIENT_PLAYBACK_EVENTS
    _PROM_OFFLINE_ELIGIBILITY = Counter(
        "offline_eligibility_checks_total",
        (
            "Offline-eligibility checks resolved by the policy "
            "adapter, labelled by allowed flag and reason code."
        ),
        ["allowed", "reason"],
        registry=registry,
    )
    _PROM_OFFLINE_PREFETCH = Counter(
        "offline_prefetch_calls_total",
        ("Prefetch API invocations by outcome " "(accepted/rejected/error)."),
        ["outcome"],
        registry=registry,
    )
    _PROM_CLIENT_PLAYBACK_EVENTS = Counter(
        "client_playback_events_total",
        "Client playback telemetry events by event name and surface.",
        ["event_name", "surface"],
        registry=registry,
    )

    from fastapi import FastAPI
    from starlette.middleware.base import (
        BaseHTTPMiddleware,
    )
    from starlette.requests import Request
    from starlette.responses import Response

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

    _PROM_REGISTRY = registry
    _attach_prometheus_metrics_route(application, registry)

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


# User-уровневые ПДн ключи (публичные имена; не секрет — могут жить
# в Backend). Дополняют admin-keys из PrivateCore. Любой ключ в
# теле события Sentry, чьё имя совпадает (case-insensitive) с этим
# списком, заменяется на "[REDACTED]" перед отправкой.
_USER_PII_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "telegram_id",
        "tg_id",
        "ip",
        "client_ip",
        "remote_addr",
        "x-forwarded-for",
        "user_agent",
        "user-agent",
        "init_data",
        "tg_init_data",
        "access_token",
        "refresh_token",
        "jwt",
        "jwt_secret",
        "session_token",
        "magic_link",
        "magic_link_url",
        "backup_code",
        "totp_secret",
        "authorization",
        "cookie",
        "set-cookie",
        "avatar_seed",
        "first_name",
        "last_name",
        "username",
    }
)


_PII_FILTER_KEYS_CACHE: frozenset[str] | None = None


def _get_blocked_pii_keys() -> frozenset[str]:
    """Build the union of admin- and user-PII keys exactly once.

    PrivateCore is imported lazily to keep the module importable in
    contexts where the dependency is not installed (e.g., minimal
    test environments).
    """
    global _PII_FILTER_KEYS_CACHE
    if _PII_FILTER_KEYS_CACHE is None:
        from dotsound_private_core.services.admin_security_policy import (
            ADMIN_PII_KEYS,
        )

        _PII_FILTER_KEYS_CACHE = frozenset(
            {key.lower() for key in ADMIN_PII_KEYS} | _USER_PII_KEYS
        )
    return _PII_FILTER_KEYS_CACHE


def _sentry_pii_filter(
    event: dict[str, object], _hint: dict[str, object]
) -> dict[str, object] | None:
    blocked = _get_blocked_pii_keys()

    def _scrub(value: object) -> object:
        if isinstance(value, dict):
            return {
                k: ("[REDACTED]" if k.lower() in blocked else _scrub(v))
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
        _PROM_LYRICS_JOBS_TOTAL.labels(tier=tier, status=status).inc()
    if _PROM_LYRICS_JOB_DURATION is not None:
        _PROM_LYRICS_JOB_DURATION.labels(tier=tier).observe(
            max(0.0, duration_seconds)
        )


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
        _PROM_HMAC_AUTH_FAILURES.labels(reason=reason).inc()


def worker_anomaly_observed(*, anomaly_type: str) -> None:
    if _PROM_WORKER_ANOMALY_TOTAL is not None:
        _PROM_WORKER_ANOMALY_TOTAL.labels(anomaly_type=anomaly_type).inc()


def worker_heartbeat_lag_observed(
    *, worker_id: str, lag_seconds: float
) -> None:
    if _PROM_WORKER_HEARTBEAT_LAG is not None:
        _PROM_WORKER_HEARTBEAT_LAG.labels(worker_id=worker_id).set(
            max(0.0, lag_seconds)
        )


def worker_jobs_in_flight_set(*, worker_id: str, count: int) -> None:
    if _PROM_WORKER_JOBS_IN_FLIGHT is not None:
        _PROM_WORKER_JOBS_IN_FLIGHT.labels(worker_id=worker_id).set(int(count))


def speechkit_spent_inc(rub: float) -> None:
    if _PROM_SPEECHKIT_SPENT is not None:
        _PROM_SPEECHKIT_SPENT.inc(max(0.0, float(rub)))


def speechkit_budget_remaining_set(rub: float) -> None:
    if _PROM_SPEECHKIT_BUDGET_REMAINING is not None:
        _PROM_SPEECHKIT_BUDGET_REMAINING.set(max(0.0, float(rub)))


def elasticsearch_query_observed(*, op: str, outcome: str) -> None:
    if _PROM_ELASTICSEARCH_QUERIES is not None:
        _PROM_ELASTICSEARCH_QUERIES.labels(op=op, outcome=outcome).inc()


def radio_request_observed(
    *,
    surface: str,
    outcome: str,
    queue_size: int,
    guard_hit: bool = False,
) -> None:
    if _PROM_RADIO_REQUESTS is not None:
        _PROM_RADIO_REQUESTS.labels(
            surface=surface,
            outcome=outcome,
        ).inc()
    if _PROM_RADIO_QUEUE_SIZE is not None:
        _PROM_RADIO_QUEUE_SIZE.labels(surface=surface).observe(
            max(0, int(queue_size))
        )
    if guard_hit and _PROM_RADIO_GUARD_HITS is not None:
        _PROM_RADIO_GUARD_HITS.labels(surface=surface).inc()


_RECSYS_LISTEN_OUTCOMES = frozenset(
    {"completed", "skipped_quick", "skipped", "partial"}
)
_RECSYS_SAVE_ACTIONS = frozenset({"like", "playlist_add", "dislike"})
_RECSYS_PIPELINE_STAGES = frozenset(
    {"retrieval", "ranking", "rerank", "total"}
)


def recsys_listen_outcome_observed(
    *,
    surface: str,
    outcome: str,
) -> None:
    if outcome not in _RECSYS_LISTEN_OUTCOMES:
        return
    if _PROM_RECSYS_LISTEN_OUTCOMES is None:
        return
    _PROM_RECSYS_LISTEN_OUTCOMES.labels(
        surface=surface,
        outcome=outcome,
    ).inc()


def recsys_save_action_observed(
    *,
    surface: str,
    action: str,
) -> None:
    if action not in _RECSYS_SAVE_ACTIONS:
        return
    if _PROM_RECSYS_SAVE_ACTIONS is None:
        return
    _PROM_RECSYS_SAVE_ACTIONS.labels(
        surface=surface,
        action=action,
    ).inc()


def recsys_pipeline_stage_observed(
    *,
    surface: str,
    stage: str,
    duration_seconds: float,
) -> None:
    if stage not in _RECSYS_PIPELINE_STAGES:
        return
    if _PROM_RECSYS_PIPELINE_LATENCY is None:
        return
    _PROM_RECSYS_PIPELINE_LATENCY.labels(
        surface=surface,
        stage=stage,
    ).observe(max(0.0, float(duration_seconds)))


def recsys_impression_position_observed(
    *,
    surface: str,
    position: int,
) -> None:
    if _PROM_RECSYS_IMPRESSION_POSITION is None:
        return
    if position < 1:
        return
    _PROM_RECSYS_IMPRESSION_POSITION.labels(
        surface=surface,
    ).observe(int(position))


def offline_eligibility_observed(
    *,
    allowed: bool,
    reason: str,
) -> None:
    """Record one offline-eligibility decision."""
    if _PROM_OFFLINE_ELIGIBILITY is None:
        return
    _PROM_OFFLINE_ELIGIBILITY.labels(
        allowed="1" if allowed else "0",
        reason=reason or "unknown",
    ).inc()


def offline_prefetch_observed(*, outcome: str) -> None:
    """Record one prefetch-API call outcome."""
    if _PROM_OFFLINE_PREFETCH is None:
        return
    _PROM_OFFLINE_PREFETCH.labels(outcome=outcome).inc()


def client_playback_event_observed(
    *,
    event_name: str,
    surface: str,
) -> None:
    if _PROM_CLIENT_PLAYBACK_EVENTS is None:
        return
    _PROM_CLIENT_PLAYBACK_EVENTS.labels(
        event_name=event_name,
        surface=surface,
    ).inc()


def tor_circuit_health_observed(
    *, circuit: int, failure_rate: float
) -> None:
    """Update the Prometheus gauge for a single Tor circuit's failure rate."""
    if _PROM_TOR_CIRCUIT_FAILURE_RATE is None:
        return
    _PROM_TOR_CIRCUIT_FAILURE_RATE.labels(
        circuit=str(circuit)
    ).set(max(0.0, min(1.0, failure_rate)))


def outbound_proxy_pool_size_set(*, size: int) -> None:
    """Set the gauge tracking active outbound proxy pool size."""
    if _PROM_OUTBOUND_PROXY_POOL_SIZE is None:
        return
    _PROM_OUTBOUND_PROXY_POOL_SIZE.set(int(size))
