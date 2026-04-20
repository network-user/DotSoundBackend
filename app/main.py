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
from app.core.db import dispose_engine
from app.core.logging import configure_logging
from app.core import log_setup  # noqa: F401 — installs debug file logs on import
from app.core.observability import (
    setup_observability,
)
from app.core.rate_limit import limiter
from app.core.redis import close_redis
from app.core.s3 import ensure_bucket_exists
from app.core.ws_manager import ws_manager
from app.middlewares.admin_security import (
    AdminSecurityMiddleware,
)
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.secure_static import SecureStaticMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging(
        settings.log_level,
        redact=settings.redact_logs,
        json_output=not settings.debug,
    )
    loop_type = type(asyncio.get_running_loop()).__name__
    logger.info(
        "sound_api_starting",
        log_level=settings.log_level,
        event_loop=loop_type,
    )
    if sys.platform == "win32" and loop_type != "ProactorEventLoop":
        logger.warning(
            "incorrect_event_loop_type",
            expected="ProactorEventLoop",
            actual=loop_type,
        )
    await ensure_bucket_exists()
    await ws_manager.startup()
    yield
    logger.info("sound_api_shutting_down")
    await ws_manager.shutdown()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    if not settings.debug and settings.jwt_secret == (
        "changeme-set-a-strong-secret-in-production"
    ):
        raise RuntimeError(
            "JWT_SECRET must be changed in production "
            "(set DEBUG=true for development)"
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

    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(SecureStaticMiddleware)
    application.add_middleware(AdminSecurityMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        max_age=3600,
    )
    hosts = settings.allowed_hosts_list
    if not settings.debug and hosts == ["*"]:
        logger.warning(
            "trusted_host_wildcard_in_production",
            hint="Set ALLOWED_HOSTS to a real list",
        )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=hosts,
    )

    application.include_router(api_router)
    application.mount(
        "/mini_app",
        StaticFiles(directory="app/static/mini_app", html=True),
        name="mini_app",
    )

    setup_observability(application)

    return application


app = create_app()
