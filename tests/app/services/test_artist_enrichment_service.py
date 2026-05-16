from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


async def test_enrich_success_queues_catalog_sync(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    info = _make_info(bio="A bio", confidence=0.9)
    provider_module = SimpleNamespace(
        fetch_artist_info=MagicMock(return_value=info),
        warmup_artist_info_provider=lambda: None,
    )

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": (
                provider_module
            ),
        },
    ), patch(
        "app.services.artist_catalog_sync_progress.set_running",
        new_callable=AsyncMock,
    ) as set_running, patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
        return_value="job-1",
    ) as enqueue:
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    set_running.assert_awaited_once()
    enqueue.assert_awaited_once()


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


async def test_enrich_not_found_queues_catalog_sync(
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
    ), patch(
        "app.services.artist_catalog_sync_progress.set_running",
        new_callable=AsyncMock,
    ), patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
        return_value="job-1",
    ) as enqueue, patch.object(
        ArtistEnrichmentService,
        "_schedule_supplemental",
        new_callable=AsyncMock,
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "not_found"
    enqueue.assert_awaited_once()


async def test_enrich_failed_queues_catalog_sync(
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
    ), patch(
        "app.services.artist_catalog_sync_progress.set_running",
        new_callable=AsyncMock,
    ), patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
        return_value="job-1",
    ) as enqueue, patch.object(
        ArtistEnrichmentService,
        "_schedule_supplemental",
        new_callable=AsyncMock,
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "failed"
    enqueue.assert_awaited_once()


async def test_enrich_skips_image_download_when_image_key_set(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    artist.image_key = "artists/1/preset.webp"
    await db_session.commit()
    info = _make_info(
        bio="updated bio",
        image_url="https://example.com/new-face.jpg",
        confidence=0.9,
    )
    mock_dl = AsyncMock(return_value="artists/1/wrong.webp")
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
        mock_dl,
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.enrichment_status == "done"
    assert artist.bio == "updated bio"
    assert artist.image_key == "artists/1/preset.webp"
    mock_dl.assert_not_called()


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


async def test_enrich_persists_source_profiles(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    profile = SimpleNamespace(
        source_id="wiki_en",
        source_name="Wikipedia (EN)",
        source_page_url=(
            "https://en.wikipedia.org/wiki/X"
        ),
        bio="wiki bio",
        birth_date=date(1990, 5, 12),
        birthplace="Berlin",
        country="de",
        image_url=None,
        website_url=None,
        discography=(
            SimpleNamespace(
                title="Album One",
                year=2018,
                type=None,
                url=None,
            ),
        ),
    )
    info = _make_info(
        bio="merged",
        confidence=0.9,
        source_profiles=(profile,),
        primary_source_id="wiki_en",
        discography=(
            SimpleNamespace(
                title="Album One",
                year=2018,
                type=None,
                url=None,
            ),
        ),
    )

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(
                    return_value=info
                ),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.primary_source_id == "wiki_en"
    assert artist.source_profiles is not None
    assert len(artist.source_profiles) == 1
    saved = artist.source_profiles[0]
    assert saved["source_id"] == "wiki_en"
    assert saved["source_name"] == "Wikipedia (EN)"
    assert saved["source_page_url"].startswith("https://")
    assert saved["bio"] == "wiki bio"
    assert saved["country"] == "DE"
    assert saved["discography"][0]["title"] == "Album One"
    assert saved["discography"][0]["year"] == 2018
    assert artist.discography is not None
    assert artist.discography[0]["title"] == "Album One"


async def test_enrich_drops_invalid_source_url(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    profile = SimpleNamespace(
        source_id="wiki_en",
        source_name="Wikipedia (EN)",
        source_page_url="javascript:alert(1)",
        bio="wiki bio",
        birth_date=None,
        birthplace=None,
        country="de",
        image_url=None,
        website_url="https://example.org",
        discography=(),
    )
    info = _make_info(
        bio="merged",
        confidence=0.9,
        source_profiles=(profile,),
        primary_source_id="wiki_en",
    )

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(
                    return_value=info
                ),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.source_profiles is not None
    saved = artist.source_profiles[0]
    assert saved["source_id"] == "wiki_en"
    assert "source_page_url" not in saved
    assert saved["website_url"] == "https://example.org"


async def test_enrich_skips_profile_without_source_id(
    db_session: AsyncSession,
) -> None:
    artist = await _make_artist(db_session)
    profile = SimpleNamespace(
        source_id="",
        source_name="Unknown",
        source_page_url="https://example.org/source",
        bio="bio",
        birth_date=None,
        birthplace=None,
        country=None,
        image_url=None,
        website_url=None,
        discography=(),
    )
    info = _make_info(
        bio="merged",
        confidence=0.9,
        source_profiles=(profile,),
        primary_source_id="wiki_en",
    )

    with patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=MagicMock(
                    return_value=info
                ),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    ):
        svc = ArtistEnrichmentService(db_session)
        await svc.enrich(artist.id)

    await db_session.refresh(artist)
    assert artist.source_profiles is None
