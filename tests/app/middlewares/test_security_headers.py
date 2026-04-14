import pytest
from httpx import AsyncClient

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
