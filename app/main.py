import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, Response
from starlette.types import Scope

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

MINI_APP_STATIC_DIR = Path(__file__).resolve().parent / "static" / "mini_app"
MINI_APP_INDEX_FILE = MINI_APP_STATIC_DIR / "index.html"
_SEO_ROOT_FILES: dict[str, str] = {
    "robots.txt": "text/plain; charset=utf-8",
    "sitemap.xml": "application/xml; charset=utf-8",
    "llms.txt": "text/plain; charset=utf-8",
}

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def resolve_seo_root_file(
    name: str,
    *,
    static_dir: Path = MINI_APP_STATIC_DIR,
) -> Path | None:
    if name not in _SEO_ROOT_FILES:
        return None
    path = static_dir / name
    if not path.is_file():
        return None
    return path


class MiniAppStaticFiles(StaticFiles):
    async def get_response(
        self,
        path: str,
        scope: Scope,
    ) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or not self._is_spa_route(path):
                raise
            return await super().get_response("index.html", scope)

        if response.status_code == 404 and self._is_spa_route(path):
            return await super().get_response("index.html", scope)
        return response

    @staticmethod
    def _is_spa_route(path: str) -> bool:
        normalized = path.replace("\\", "/").strip("/")
        if not normalized:
            return False
        first_segment = normalized.split("/", 1)[0]
        if first_segment in {"assets", "sounds"}:
            return False
        return PurePosixPath(normalized).suffix == ""


async def _elasticsearch_drain_lifecycle(
    stop: asyncio.Event,
) -> None:
    from app.services.search_playcount_drain import (
        playcount_drain_loop,
    )

    await playcount_drain_loop(stop)


async def _warm_outbound_proxy_pool() -> None:
    """Fire a lightweight GET through every configured proxy URL.

    This establishes SOCKS5 tunnels and TCP/TLS connections up-front
    so the first real audio request does not pay the handshake cost.
    Runs as a fire-and-forget background task; failures are suppressed.
    """
    import contextlib

    import httpx

    from app.api.v1.tracks.playback import _get_audio_proxy_client

    proxy_urls: list[str] = list(settings.outbound_static_proxy_urls_list)
    if not proxy_urls:
        from app.services.tor_pool import get_tor_pool

        pool = get_tor_pool()
        if pool is not None:
            proxy_urls = pool.circuit_proxy_urls()

    if not proxy_urls:
        return

    warmup_url = "https://api.ipify.org"
    warmed = 0
    for proxy_url in proxy_urls:
        client = _get_audio_proxy_client(proxy_url)
        with contextlib.suppress(Exception):
            await client.get(
                warmup_url,
                timeout=httpx.Timeout(15.0, connect=10.0),
            )
            warmed += 1

    logger.info(
        "outbound_proxy_pool_warmed",
        warmed=warmed,
        total=len(proxy_urls),
    )


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

    try:
        from app.services.sc_client_id_manager import initialize as _sc_init

        await _sc_init()
    except Exception as _sc_exc:  # noqa: BLE001
        logger.warning("sc_client_id_init_failed", error=str(_sc_exc)[:200])

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

            _es_init_bg_task = asyncio.create_task(_es_init_background())
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
        from app.services.background_jobs_cleanup_worker import (
            ensure_default_cleanup_schedule,
        )

        await ensure_default_cleanup_schedule()
    except Exception as exc:
        logger.warning(
            "background_jobs_cleanup_schedule_seed_failed",
            error=str(exc)[:200],
        )

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

    from app.services.tor_pool import start_tor_pool_from_settings

    _tor_pool_started = await start_tor_pool_from_settings(
        settings,
        component="api",
    )
    if _tor_pool_started:
        from dotsound_private_core.services.outbound import (
            reset_outbound_quarantine,
        )

        from app.api.v1.tracks.playback import reset_audio_proxy_clients
        from app.services.tor_pool import get_tor_pool as _gtp

        _tp = _gtp()
        if _tp is not None:
            _tp.register_newnym_callback(reset_audio_proxy_clients)
            _tp.register_newnym_callback(reset_outbound_quarantine)

    if _tor_pool_started or settings.outbound_static_proxy_urls_list:
        asyncio.create_task(
            _warm_outbound_proxy_pool(),
            name="outbound_proxy_warmup",
        )

    try:
        from app.core.observability import outbound_proxy_pool_size_set
        from app.services.tor_pool import get_tor_pool as _gtp2

        _proxy_pool_size = len(settings.outbound_static_proxy_urls_list)
        if _tor_pool_started:
            _tp2 = _gtp2()
            if _tp2 is not None:
                _proxy_pool_size = len(_tp2.circuit_proxy_urls())
        if _proxy_pool_size:
            outbound_proxy_pool_size_set(size=_proxy_pool_size)
    except Exception:
        pass
    resource_stop: asyncio.Event | None = None
    resource_task: asyncio.Task[None] | None = None
    if settings.system_resource_sampler_enabled:
        from app.services.system_resource_service import (
            system_resource_sampler_loop,
        )

        resource_stop = asyncio.Event()
        resource_task = asyncio.create_task(
            system_resource_sampler_loop(resource_stop),
            name="system_resource_sampler",
        )
        application.state._system_resource_sampler_task = resource_task

    startup_alert_task: asyncio.Task[None] | None = None
    if settings.admin_startup_alert_enabled:
        from app.services.admin_alert_service import (
            send_startup_alert_with_retries,
        )

        startup_alert_task = asyncio.create_task(
            send_startup_alert_with_retries(component="api"),
            name="startup_admin_alert",
        )
        application.state._startup_alert_task = startup_alert_task

    yield

    if startup_alert_task is not None and not startup_alert_task.done():
        startup_alert_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await startup_alert_task
    if resource_stop is not None and resource_task is not None:
        resource_stop.set()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(resource_task, timeout=5.0)
    if _tor_pool_started:
        from app.services.tor_pool import stop_tor_pool_from_settings

        await stop_tor_pool_from_settings(component="api")
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
    try:
        from app.api.v1.tracks.playback import close_audio_proxy_clients

        await close_audio_proxy_clients()
    except Exception:  # noqa: BLE001
        logger.exception("audio_proxy_client_close_failed")
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

    def _seo_file_response(name: str) -> Response:
        media_type = _SEO_ROOT_FILES[name]
        file_path = resolve_seo_root_file(name)
        if file_path is None:
            return Response(status_code=404)
        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )

    @application.get("/robots.txt", include_in_schema=False)
    async def robots_txt() -> Response:
        return _seo_file_response("robots.txt")

    @application.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_xml() -> Response:
        return _seo_file_response("sitemap.xml")

    @application.get("/llms.txt", include_in_schema=False)
    async def llms_txt() -> Response:
        return _seo_file_response("llms.txt")

    if MINI_APP_INDEX_FILE.is_file():
        application.mount(
            "/mini_app",
            MiniAppStaticFiles(
                directory=str(MINI_APP_STATIC_DIR),
                html=True,
            ),
            name="mini_app",
        )
    else:
        structlog.get_logger(__name__).warning(
            "mini_app_static_missing",
            path=str(MINI_APP_STATIC_DIR),
            index_path=str(MINI_APP_INDEX_FILE),
        )

    setup_observability(application)

    return application


app = create_app()
