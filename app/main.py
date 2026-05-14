import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.config import settings
from app.core import (
    log_setup,  # noqa: F401 — installs debug file logs on import
)
from app.core.db import dispose_engine
from app.core.logging import configure_logging
from app.core.observability import (
    setup_observability,
)
from app.core.rate_limit import limiter
from app.core.redis import close_redis
from app.core.s3 import ensure_bucket_exists
from app.core.ws_manager import ws_manager
from app.middlewares.admin_audit_log import (
    AdminAuditLogMiddleware,
)
from app.middlewares.admin_security import (
    AdminSecurityMiddleware,
)
from app.middlewares.internal_api_allowlist import (
    InternalApiAllowlistMiddleware,
)
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.secure_static import SecureStaticMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _elasticsearch_drain_lifecycle(
    stop: asyncio.Event,
) -> None:
    from app.services.search_playcount_drain import (
        playcount_drain_loop,
    )

    await playcount_drain_loop(stop)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging(
        settings.log_level,
        redact=settings.redact_logs,
        redact_identifiers=settings.redact_log_identifiers,
        json_output=not settings.debug,
        third_party_level=settings.log_third_party_level,
    )
    loop_type = type(asyncio.get_running_loop()).__name__
    logger.info(
        "sound_api_starting",
        log_level=settings.log_level,
        event_loop=loop_type,
    )
    _n_static = len(settings.outbound_static_proxy_urls_list)
    if _n_static:
        logger.info(
            "outbound_static_proxies_configured",
            count=_n_static,
        )
    if sys.platform == "win32" and loop_type != "ProactorEventLoop":
        logger.warning(
            "incorrect_event_loop_type",
            expected="ProactorEventLoop",
            actual=loop_type,
        )
    await ensure_bucket_exists()
    await ws_manager.startup()

    play_stop: asyncio.Event | None = None
    drain_task: asyncio.Task[None] | None = None
    if (
        settings.elasticsearch_enabled
        and (settings.elasticsearch_url or "").strip()
    ):
        from app.search.es_client import es_available
        from app.services.search_index_service import (
            count_tracks_indexed,
            init_elasticsearch_starter,
        )

        if es_available():
            _do_backfill = settings.elasticsearch_backfill_on_empty or (
                settings.elasticsearch_dev_bootstrap
            )

            async def _es_init_background() -> None:
                try:
                    await init_elasticsearch_starter()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("elasticsearch_init_failed", error=str(exc))
                    return
                if _do_backfill:
                    try:
                        n = await count_tracks_indexed()
                        if n < 1:
                            from app.services import search_index_worker

                            await (
                                search_index_worker.reindex_backfill_all_task.kiq()
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "elasticsearch_backfill_kiq_failed",
                            error=str(exc),
                        )

            _es_init_bg_task = asyncio.create_task(
                _es_init_background()
            )
            application.state._es_init_bg_task = _es_init_bg_task
            play_stop = asyncio.Event()
            drain_task = asyncio.create_task(
                _elasticsearch_drain_lifecycle(play_stop)
            )

    try:
        from app.core.db import AsyncSessionLocal
        from app.repositories.app_settings import AppSettingsRepository
        from app.services import artist_backfill_worker

        async with AsyncSessionLocal() as _s:
            _done = await AppSettingsRepository(_s).get(
                artist_backfill_worker._SETTING_KEY
            )
        if _done is None:
            await artist_backfill_worker.artist_link_backfill_task.kiq()
            logger.info("artist_link_backfill_enqueued")
    except Exception as exc:
        logger.warning("artist_link_backfill_enqueue_failed", error=str(exc))

    try:
        from app.core.db import AsyncSessionLocal as _ASL
        from app.repositories.app_settings import AppSettingsRepository as _ASR
        from app.services import waveform_worker

        async with _ASL() as _ws:
            _wdone = await _ASR(_ws).get(waveform_worker._SETTING_KEY)
        if _wdone is None:
            await waveform_worker.waveform_backfill_task.kiq()
            logger.info("waveform_backfill_enqueued")
    except Exception as exc:
        logger.warning("waveform_backfill_enqueue_failed", error=str(exc))

    _tor_pool_started = False
    if settings.tor_pool_enabled:
        from app.services.tor_pool import TorPool, _set_tor_pool

        _tp = TorPool(settings)
        try:
            await _tp.start()
            _set_tor_pool(_tp)
            _tor_pool_started = True
        except Exception as _exc:
            logger.error(
                "tor_pool_start_failed",
                error=str(_exc),
                hint="Install Tor (apt) or Tor Browser/Expert (Windows).",
            )

    yield

    if _tor_pool_started:
        from app.services.tor_pool import _set_tor_pool, get_tor_pool

        _pool = get_tor_pool()
        if _pool is not None:
            await _pool.stop()
        _set_tor_pool(None)
    logger.info("sound_api_shutting_down")
    if play_stop is not None and drain_task is not None:
        play_stop.set()
        try:
            await asyncio.wait_for(drain_task, timeout=10.0)
        except TimeoutError:
            logger.warning("elasticsearch_drain_task_timeout")
    if (
        settings.elasticsearch_enabled
        and (settings.elasticsearch_url or "").strip()
    ):
        from app.search.es_client import close_es

        try:
            await close_es()
        except Exception:  # noqa: BLE001
            logger.exception("elasticsearch_close_failed")
    try:
        from app.services.soundcloud_service import close_sc_http_clients

        await close_sc_http_clients()
    except Exception:  # noqa: BLE001
        logger.exception("sc_http_client_close_failed")
    await ws_manager.shutdown()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a strong random value "
            "(>= 32 chars); see deployment docs."
        )

    application = FastAPI(
        title=".Sound API",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.state.limiter = limiter
    application.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

    from app.middlewares.abuse_signal import (
        AbuseSignalMiddleware,
    )
    from app.middlewares.body_size_limit import (
        BodySizeLimitMiddleware,
    )
    from app.middlewares.csrf import CSRFMiddleware

    application.add_middleware(BodySizeLimitMiddleware)
    application.add_middleware(CSRFMiddleware)
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(SecureStaticMiddleware)
    application.add_middleware(AdminSecurityMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(InternalApiAllowlistMiddleware)
    application.add_middleware(AbuseSignalMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-CSRF-Token",
            "Idempotency-Key",
        ],
        max_age=3600,
    )
    hosts = settings.allowed_hosts_list
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=hosts,
    )
    application.add_middleware(AdminAuditLogMiddleware)

    application.include_router(api_router)
    application.mount(
        "/mini_app",
        StaticFiles(directory="app/static/mini_app", html=True),
        name="mini_app",
    )

    setup_observability(application)

    return application


app = create_app()
