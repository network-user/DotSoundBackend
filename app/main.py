from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.db import dispose_engine
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    application = FastAPI(
        title="DotSoundBackend",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    application.mount(
        "/mini_app",
        StaticFiles(directory="app/static/mini_app", html=True),
        name="mini_app",
    )
    return application


app = create_app()
