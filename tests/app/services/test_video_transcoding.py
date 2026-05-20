import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services import video_transcoding

pytestmark = pytest.mark.anyio


async def test_update_video_status_skips_stale_token(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> None:
            return None

    def session_factory() -> SessionContext:
        return SessionContext()

    monkeypatch.setattr(
        video_transcoding, "AsyncSessionLocal", session_factory
    )

    user = User(telegram_id=8300, first_name="Video")
    db_session.add(user)
    await db_session.flush()
    track = Track(
        title="Race",
        uploaded_by_id=user.id,
        video_processing_status="processing:old",
    )
    db_session.add(track)
    await db_session.commit()

    updated = await video_transcoding._update_video_status(
        track.id,
        "active",
        video_key="videos/new.mp4",
        expected_status="processing:new",
    )

    assert updated is False
    await db_session.refresh(track)
    assert track.video_processing_status == "processing:old"
    assert track.video_key is None

    updated = await video_transcoding._update_video_status(
        track.id,
        "active",
        video_key="videos/new.mp4",
        expected_status="processing:old",
    )

    assert updated is True
    await db_session.refresh(track)
    assert track.video_processing_status == "active"
    assert track.video_key == "videos/new.mp4"
