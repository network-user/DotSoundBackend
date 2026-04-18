from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.repositories.artist import ArtistRepository
from app.services.artist_enrichment_service import (
    ArtistEnrichmentService,
    ArtistNotFound,
)

pytestmark = pytest.mark.anyio


def _make_info(**overrides):
    defaults = dict(
        bio=None,
        birth_date=None,
        birthplace=None,
        country=None,
        image_url=None,
        website_url=None,
        confidence=0.9,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def _make_artist(
    session: AsyncSession, name: str = "Someone"
) -> Artist:
    repo = ArtistRepository(session)
    artist = await repo.create(
        name=name,
        name_normalized=name.lower(),
        source="internal",
        external_id=None,
    )
    await session.commit()
    return artist


async def test_enrich_success_full_info(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(
        bio="A long biography",
        birth_date=date(1990, 5, 12),
        birthplace="Moscow",
        country="ru",
        website_url="https://example.com/a",
        confidence=0.9,
    )

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=info),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "done"
    assert artist.bio == "A long biography"
    assert artist.birth_date == date(1990, 5, 12)
    assert artist.birthplace == "Moscow"
    assert artist.country == "RU"
    assert artist.website_url == "https://example.com/a"
    assert artist.enriched_at is not None


async def test_enrich_partial_info_keeps_status_done(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(bio="Only a bio", confidence=0.8)

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=info),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "done"
    assert artist.bio == "Only a bio"
    assert artist.birth_date is None


async def test_enrich_returns_none_sets_not_found(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=None),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "not_found"
    assert artist.bio is None


async def test_enrich_low_confidence_sets_not_found(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(bio="maybe", confidence=0.1)

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=info),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "not_found"
    assert artist.bio is None


async def test_enrich_provider_raises_sets_failed(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=_boom,
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "failed"
    assert artist.enriched_at is not None


async def test_enrich_image_download_failure_keeps_text(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(
        bio="kept",
        image_url="https://example.com/not-a-real-image",
        confidence=0.9,
    )

    async def _fail_image(self, image_url):
        raise RuntimeError("network down")

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=info),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ), patch.object(
        ArtistEnrichmentService,
        "_download_and_store_image",
        _fail_image,
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "done"
    assert artist.bio == "kept"
    assert artist.image_key is None


async def test_enrich_missing_artist_raises(
    db_session: AsyncSession,
) -> None:
    svc = ArtistEnrichmentService(db_session)
    with pytest.raises(ArtistNotFound):
        await svc.enrich(999999)


async def test_enrich_bio_truncation(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(bio="x" * 20000, confidence=0.9)

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(return_value=info),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.bio is not None
    assert len(artist.bio) == 8000
