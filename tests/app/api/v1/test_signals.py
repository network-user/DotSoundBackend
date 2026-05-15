import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def _quick_track(
    client: AsyncClient,
    user_id: int,
) -> int:
    headers = await auth_headers(client, user_id)
    await client.get(
        "/api/v1/tracks/?size=1", headers=headers
    )
    return 1


async def test_record_listen_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": 100,
        },
    )
    assert r.status_code == 401


async def test_record_listen(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9001)
    headers = await auth_headers(client, 9001)

    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": 120,
            "total_duration": 200,
            "source_context": "home",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_record_search(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9002)
    headers = await auth_headers(client, 9002)

    r = await client.post(
        "/api/v1/signals/search",
        json={
            "query": "drake",
            "results_count": 5,
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_record_client_playback_event(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await create_test_user(client, 9004)
    headers = await auth_headers(client, 9004)
    observed: list[tuple[str, str]] = []

    def fake_observed(
        *,
        event_name: str,
        surface: str,
    ) -> None:
        observed.append((event_name, surface))

    monkeypatch.setattr(
        "app.api.v1.signals.client_playback_event_observed",
        fake_observed,
    )

    r = await client.post(
        "/api/v1/signals/client/playback-event",
        json={
            "event_name": "radio_auto_skip_exhausted",
            "surface": "radio",
            "current_track_id": 12,
            "radio_seed_track_id": 10,
            "consecutive_skips": 3,
            "queue_size": 0,
            "error_code": "soundcloud_stream_unavailable",
            "error_reason": (
                "provider_manifest_not_found_for_all_formats"
            ),
        },
        headers=headers,
    )

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert observed == [("radio_auto_skip_exhausted", "radio")]


async def test_record_client_playback_event_rejects_unknown_event(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9005)
    headers = await auth_headers(client, 9005)

    r = await client.post(
        "/api/v1/signals/client/playback-event",
        json={
            "event_name": "unknown",
            "surface": "radio",
            "consecutive_skips": 3,
        },
        headers=headers,
    )

    assert r.status_code == 422


async def test_record_listen_invalid(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 9003)
    headers = await auth_headers(client, 9003)

    r = await client.post(
        "/api/v1/signals/listen",
        json={
            "track_id": 1,
            "duration_listened": -1,
        },
        headers=headers,
    )
    assert r.status_code == 422
