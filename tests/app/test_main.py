from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette

from app.main import MiniAppStaticFiles

pytestmark = pytest.mark.anyio


def _write_mini_app_index(static_dir: Path) -> None:
    static_dir.joinpath("index.html").write_text(
        "<!doctype html><div id=\"root\"></div>",
        encoding="utf-8",
    )


async def test_mini_app_static_files_serves_index_for_spa_route(
    tmp_path: Path,
) -> None:
    _write_mini_app_index(tmp_path)
    application = Starlette()
    application.mount(
        "/mini_app",
        MiniAppStaticFiles(directory=str(tmp_path), html=True),
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        root = await client.get("/mini_app/")
        deep_link = await client.get("/mini_app/track/123")

    assert root.status_code == 200
    assert deep_link.status_code == 200
    assert deep_link.headers["content-type"].startswith("text/html")
    assert deep_link.text == root.text


async def test_mini_app_static_files_missing_asset_stays_404(
    tmp_path: Path,
) -> None:
    _write_mini_app_index(tmp_path)
    tmp_path.joinpath("assets").mkdir()
    application = Starlette()
    application.mount(
        "/mini_app",
        MiniAppStaticFiles(directory=str(tmp_path), html=True),
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/mini_app/assets/not-found.js")

    assert response.status_code == 404
