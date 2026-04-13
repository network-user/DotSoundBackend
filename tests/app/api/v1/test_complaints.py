import pytest
from dirty_equals import (
    IsInstance,
    IsPartialDict,
    IsStr,
)
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_submit_complaint(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10001)
    track = await create_test_track(
        client, "DMCA Test", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.post(
        "/api/v1/complaints",
        json={
            "track_id": track["id"],
            "reason": (
                "Нарушение авторских прав:"
                " трек принадлежит мне"
            ),
            "contact_email": "rights@example.com",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        complaint=IsPartialDict(
            track_id=track["id"],
            reason=IsStr(regex=r"^Нарушение.*"),
            contact_email="rights@example.com",
        ),
        track_hidden=IsInstance(bool),
    )


async def test_duplicate_complaint_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10002)
    track = await create_test_track(
        client, "DupComplaint", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    payload = {
        "track_id": track["id"],
        "reason": (
            "Повторная жалоба на тот же трек"
            " проверка"
        ),
    }
    r1 = await client.post(
        "/api/v1/complaints",
        json=payload,
        headers=headers,
    )
    r2 = await client.post(
        "/api/v1/complaints",
        json=payload,
        headers=headers,
    )
    assert r1.status_code == 200
    assert r2.status_code == 409


async def test_list_complaints(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10003)
    track = await create_test_track(
        client, "ListComplaint", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    await client.post(
        "/api/v1/complaints",
        json={
            "track_id": track["id"],
            "reason": (
                "Нарушение: незаконное"
                " использование записи"
            ),
        },
        headers=headers,
    )

    r = await client.get(
        f"/api/v1/complaints/{track['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert IsInstance(list) == r.json()
    assert any(
        c["track_id"] == track["id"]
        for c in r.json()
    )


async def test_track_auto_hidden_at_threshold(
    client: AsyncClient,
) -> None:
    from app.config import settings

    threshold = settings.complaint_threshold
    track_owner = await create_test_user(
        client, 19999
    )
    track = await create_test_track(
        client, "ThresholdTrack", track_owner["id"]
    )
    track_id = track["id"]

    for i in range(threshold):
        tg_id = 20000 + i
        user = await create_test_user(
            client, tg_id
        )
        headers = await auth_headers(
            client, user["id"]
        )
        r = await client.post(
            "/api/v1/complaints",
            json={
                "track_id": track_id,
                "reason": (
                    f"Жалоба #{i + 1}"
                    " на авторское право"
                ),
            },
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        if i == threshold - 1:
            assert data["track_hidden"] is True
