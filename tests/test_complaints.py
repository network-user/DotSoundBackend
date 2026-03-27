import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


pytestmark = pytest.mark.anyio


async def _create_user(client: AsyncClient, tg_id: int) -> int:
    resp = await client.post(
        "/api/v1/users",
        json={"telegram_id": tg_id, "username": f"user{tg_id}"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def _create_track(
    client: AsyncClient, uploader_id: int
) -> int:
    fake_audio = b"ID3" + b"\x00" * 128
    with patch(
        "app.services.upload_service.UploadService."
        "_upload_audio_to_s3",
        new_callable=AsyncMock,
        return_value=f"test/{uploader_id}/track.mp3",
    ):
        resp = await client.post(
            "/api/v1/tracks/upload",
            files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
            data={
                "title": "Test Track",
                "uploader_id": str(uploader_id),
            },
        )
    if resp.status_code not in (200, 201):
        resp2 = await client.post(
            "/api/v1/tracks/upload",
            files={
                "file": ("test.mp3", fake_audio, "audio/mpeg")
            },
            data={
                "title": "Test Track",
                "uploader_id": str(uploader_id),
            },
        )
        return resp2.json().get("id", 1)
    return resp.json()["id"]


async def test_submit_complaint(client: AsyncClient) -> None:
    uid = await _create_user(client, tg_id=10001)

    with (
        patch(
            "app.services.upload_service.UploadService."
            "_upload_audio_to_s3",
            new_callable=AsyncMock,
            return_value="test/10001/track.mp3",
        ),
        patch(
            "app.core.s3.upload_audio",
            new_callable=AsyncMock,
            return_value="test/10001/track.mp3",
        ),
    ):
        resp = await client.post(
            "/api/v1/tracks/upload",
            files={
                "file": (
                    "test.mp3",
                    b"ID3" + b"\x00" * 128,
                    "audio/mpeg",
                )
            },
            data={"title": "DMCA Test", "uploader_id": str(uid)},
        )
    track_id = resp.json().get("id", 1)

    r = await client.post(
        "/api/v1/complaints",
        json={
            "track_id": track_id,
            "reported_by_user_id": uid,
            "reason": "Нарушение авторских прав: трек принадлежит мне",
            "contact_email": "rights@example.com",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["complaint"]["track_id"] == track_id
    assert data["complaint"]["reason"].startswith("Нарушение")
    assert data["complaint"]["contact_email"] == "rights@example.com"
    assert isinstance(data["track_hidden"], bool)


async def test_duplicate_complaint_rejected(
    client: AsyncClient,
) -> None:
    uid = await _create_user(client, tg_id=10002)

    payload = {
        "track_id": 999,
        "reported_by_user_id": uid,
        "reason": "Повторная жалоба на тот же трек проверка",
        "contact_email": None,
    }
    r1 = await client.post("/api/v1/complaints", json=payload)
    r2 = await client.post("/api/v1/complaints", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 409


async def test_list_complaints(client: AsyncClient) -> None:
    uid = await _create_user(client, tg_id=10003)
    track_id = 888

    await client.post(
        "/api/v1/complaints",
        json={
            "track_id": track_id,
            "reported_by_user_id": uid,
            "reason": "Нарушение: незаконное использование записи",
        },
    )

    r = await client.get(f"/api/v1/complaints/{track_id}")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert any(c["track_id"] == track_id for c in items)


async def test_track_auto_hidden_at_threshold(
    client: AsyncClient,
) -> None:
    from app.config import settings

    threshold = settings.complaint_threshold
    track_id = 777

    for i in range(threshold):
        tg_id = 20000 + i
        uid = await _create_user(client, tg_id=tg_id)
        r = await client.post(
            "/api/v1/complaints",
            json={
                "track_id": track_id,
                "reported_by_user_id": uid,
                "reason": f"Жалоба #{i + 1} на авторское право",
            },
        )
        assert r.status_code == 200
        data = r.json()
        if i == threshold - 1:
            assert data["track_hidden"] is True
