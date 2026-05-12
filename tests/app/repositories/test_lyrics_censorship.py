"""Verify LyricsRepository applies text censorship before writing to DB."""
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.lyrics import LyricsRepository
from tests.factories import TrackFactory, UserFactory

pytestmark = pytest.mark.anyio

_WORDS = frozenset({"запрещено"})

_patch_keywords = patch(
    "dotsound_private_core.services.text_censorship._BANNED_KEYWORDS",
    _WORDS,
)
_patch_pattern = patch(
    "dotsound_private_core.services.text_censorship._PATTERN",
    None,
)


async def _make_track(session: AsyncSession) -> int:
    user = UserFactory()
    session.add(user)
    await session.flush()
    track = TrackFactory(uploaded_by_id=user.id)
    session.add(track)
    await session.flush()
    return track.id


async def test_create_or_update_censors_plain_text(
    session: AsyncSession,
) -> None:
    track_id = await _make_track(session)
    repo = LyricsRepository(session)
    with _patch_keywords, _patch_pattern:
        lyrics = await repo.create_or_update(
            track_id, "слово запрещено здесь"
        )
    assert "запрещено" not in lyrics.plain_text
    assert "з*******о" in lyrics.plain_text


async def test_create_or_update_censors_synced_lines(
    session: AsyncSession,
) -> None:
    track_id = await _make_track(session)
    repo = LyricsRepository(session)
    lines = [
        {"line": "это запрещено!", "startTimeMs": 0},
        {"line": "чисто", "startTimeMs": 500},
    ]
    with _patch_keywords, _patch_pattern:
        lyrics = await repo.create_or_update(
            track_id,
            "текст",
            synced_lines=lines,
        )
    assert lyrics.synced_lines is not None
    assert "запрещено" not in lyrics.synced_lines[0]["line"]
    assert lyrics.synced_lines[1]["line"] == "чисто"


async def test_update_sync_censors_lines(
    session: AsyncSession,
) -> None:
    track_id = await _make_track(session)
    repo = LyricsRepository(session)
    with _patch_keywords, _patch_pattern:
        await repo.create_or_update(track_id, "текст")
        updated = await repo.update_sync(
            track_id,
            [{"line": "запрещено слово", "startTimeMs": 0}],
        )
    assert updated is not None
    assert "запрещено" not in updated.synced_lines[0]["line"]
