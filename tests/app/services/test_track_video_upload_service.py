from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.track_video_upload_service import (
    normalize_video_upload_content_type,
    upload_track_video_bytes,
)

pytestmark = pytest.mark.anyio


class TestNormalizeVideoUploadContentType:
    def test_quicktime_maps_to_mp4(self) -> None:
        assert (
            normalize_video_upload_content_type(
                "video/quicktime"
            )
            == "video/mp4"
        )

    def test_empty_returns_none(self) -> None:
        assert normalize_video_upload_content_type(None) is None
        assert (
            normalize_video_upload_content_type(
                "application/octet-stream"
            )
            is None
        )


async def test_upload_queues_transcode_for_large_mp4(
    db_session: AsyncSession,
) -> None:
    user = User(telegram_id=8401, first_name="Vid")
    db_session.add(user)
    await db_session.flush()
    track = Track(title="Big", uploaded_by_id=user.id)
    db_session.add(track)
    await db_session.commit()

    video_data = b"\x00\x00\x00\x1cftypisom" + (b"\x00" * 200)
    with (
        patch(
            "app.services.track_video_upload_service."
            "should_fast_attach_track_video",
            return_value=False,
        ),
        patch(
            "app.services.track_video_upload_service."
            "validate_video_async",
            new_callable=AsyncMock,
            return_value="video/mp4",
        ),
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.video_transcoding.transcode_video.kiq",
            new_callable=AsyncMock,
        ) as mock_kiq,
    ):
        await upload_track_video_bytes(
            db_session,
            track,
            video_data,
            "video/mp4",
            "clip.mp4",
        )

    assert track.video_processing_status.startswith(
        "processing:"
    )
    mock_kiq.assert_awaited_once()
