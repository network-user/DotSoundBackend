import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import admin_bearer_for_user, create_test_user

pytestmark = pytest.mark.anyio


async def test_admin_radio_auto_skip_reasons_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_test_user(client, 130101)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    calls: list[tuple[int, int]] = []

    async def fake_stats(
        *,
        days: int,
        limit: int,
    ) -> list[dict[str, int | str]]:
        calls.append((days, limit))
        return [
            {
                "error_code": "soundcloud_stream_unavailable",
                "error_reason": "provider_manifest_not_found",
                "count": 3,
            }
        ]

    monkeypatch.setattr(
        "app.api.v1.admin.dashboard.get_radio_auto_skip_reason_stats",
        fake_stats,
    )

    r = await client.get(
        "/api/v1/admin/dashboard/radio-auto-skip-reasons",
        headers=headers,
        params={"days": 7, "limit": 5},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    assert body["items"] == [
        {
            "error_code": "soundcloud_stream_unavailable",
            "error_reason": "provider_manifest_not_found",
            "count": 3,
        }
    ]
    assert calls == [(7, 5)]
