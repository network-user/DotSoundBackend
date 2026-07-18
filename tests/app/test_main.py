from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import FileResponse, Response

from app.main import (
    MiniAppStaticFiles,
    _SEO_ROOT_FILES,
    resolve_seo_root_file,
)

pytestmark = pytest.mark.anyio


def _write_mini_app_index(static_dir: Path) -> None:
    static_dir.joinpath("index.html").write_text(
        "<!doctype html><div id=\"root\"></div>",
        encoding="utf-8",
    )


def _write_seo_files(static_dir: Path) -> None:
    static_dir.joinpath("robots.txt").write_text(
        "User-agent: *\nDisallow: /api/\n",
        encoding="utf-8",
    )
    static_dir.joinpath("sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset></urlset>',
        encoding="utf-8",
    )
    static_dir.joinpath("llms.txt").write_text(
        "# DotSound\n",
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


def test_resolve_seo_root_file_known_names(tmp_path: Path) -> None:
    _write_seo_files(tmp_path)
    for name in _SEO_ROOT_FILES:
        resolved = resolve_seo_root_file(
            name,
            static_dir=tmp_path,
        )
        assert resolved is not None
        assert resolved.name == name


def test_resolve_seo_root_file_rejects_unknown(
    tmp_path: Path,
) -> None:
    assert (
        resolve_seo_root_file(
            "secret.env",
            static_dir=tmp_path,
        )
        is None
    )


async def test_seo_root_files_served_when_present(
    tmp_path: Path,
) -> None:
    _write_seo_files(tmp_path)
    application = Starlette()

    def make_handler(name: str):
        async def handler() -> Response:
            media_type = _SEO_ROOT_FILES[name]
            file_path = resolve_seo_root_file(
                name,
                static_dir=tmp_path,
            )
            if file_path is None:
                return Response(status_code=404)
            return FileResponse(
                path=file_path,
                media_type=media_type,
            )

        return handler

    for name in _SEO_ROOT_FILES:
        application.add_route(
            f"/{name}",
            make_handler(name),
            methods=["GET"],
        )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        robots = await client.get("/robots.txt")
        sitemap = await client.get("/sitemap.xml")
        llms = await client.get("/llms.txt")

    assert robots.status_code == 200
    assert "Disallow: /api/" in robots.text
    assert sitemap.status_code == 200
    assert "urlset" in sitemap.text
    assert llms.status_code == 200
    assert "DotSound" in llms.text
