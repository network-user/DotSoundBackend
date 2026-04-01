# --- WINDOWS ASYNCIO FIX ---
# Должно быть выполнено до создания любого цикла событий
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ---------------------------

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
from app.core.s3 import ensure_bucket_exists
from app.core.rate_limit import limiter
from app.middlewares.request_logging import RequestLoggingMiddleware

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
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
            hint="Subprocesses (ffmpeg) will fail with NotImplementedError",
        )
    await ensure_bucket_exists()
    yield
    logger.info("sound_api_shutting_down")
    await dispose_engine()


def create_app() -> FastAPI:
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
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],
    )

    application.include_router(api_router)
    application.mount(
        "/mini_app",
        StaticFiles(directory="app/static/mini_app", html=True),
        name="mini_app",
    )

    return application


app = create_app()
