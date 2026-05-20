import pytest
from httpx import AsyncClient

from app.main import MINI_APP_INDEX_FILE

pytestmark = pytest.mark.anyio


async def test_nosniff_on_api_response(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert (
        r.headers.get("x-content-type-options")
        == "nosniff"
    )


async def test_no_csp_on_json_response(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/health")
    assert (
        "content-security-policy" not in r.headers
    )


@pytest.mark.skipif(
    not MINI_APP_INDEX_FILE.is_file(),
    reason="mini_app static build missing",
)
async def test_html_csp_allows_soundcloud_widget_frame(
    client: AsyncClient,
) -> None:
    r = await client.get("/mini_app/")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "frame-src" in csp
    assert "https://w.soundcloud.com" in csp
