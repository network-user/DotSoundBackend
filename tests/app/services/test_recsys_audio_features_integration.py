from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures
from app.services.track_features_builder import (
    build_track_features,
)

pytestmark = pytest.mark.anyio


async def test_builder_reads_audio_vector_when_row_exists(
    db_session: AsyncSession,
) -> None:
    t = Track(
        title="x",
        source="internal",
    )
    db_session.add(t)
    await db_session.flush()
    db_session.add(
        TrackAudioFeatures(
            track_id=t.id,
            feature_vector=[0.1, 0.2, 0.3],
            mood_tags=["m1"],
        )
    )
    await db_session.commit()
    feats = await build_track_features(
        db_session,
        [t],
    )
    assert len(feats) == 1
    f = feats[0]
    assert f.audio_feature_vector is not None
    assert abs(f.audio_feature_vector[0] - 0.1) < 0.01
    assert f.mood_tags == ["m1"]


async def test_builder_degrades_without_row(
    db_session: AsyncSession,
) -> None:
    t = Track(
        title="y",
        source="internal",
    )
    db_session.add(t)
    await db_session.commit()
    feats = await build_track_features(
        db_session,
        [t],
    )
    assert feats[0].audio_feature_vector is None
    assert feats[0].mood_tags == []
