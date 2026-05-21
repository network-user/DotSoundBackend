import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bandcamp_service import BandcampService, _bc_search_from_html


def test_bc_search_from_html_strips_search_query() -> None:
    html = (
        '<a href="https://foo.bandcamp.com/track/some-slug?'
        "from=search&amp;search_item_id=1&amp;search_item_type=t\">x</a>"
    )
    rows = _bc_search_from_html(html, 10)
    assert len(rows) == 1
    assert rows[0]["track_url"] == "https://foo.bandcamp.com/track/some-slug"


def test_bc_search_from_html_deduplicates() -> None:
    h = "https://foo.bandcamp.com/track/slug?from=search"
    html = f'<a href="{h}">a</a><a href="{h}">b</a>'
    rows = _bc_search_from_html(html, 10)
    assert len(rows) == 1


@pytest.mark.anyio
async def test_import_or_get_track_creates_ownerless_external_reference(
    db_session: AsyncSession,
) -> None:
    svc = BandcampService(db_session)

    track = await svc.import_or_get_track(
        {
            "_bc_page_url": "https://artist.bandcamp.com/track/song",
            "artist": "Artist",
            "trackinfo": [
                {
                    "track_id": 42,
                    "title": "BC Song",
                    "duration": 120,
                }
            ],
        },
        uploader_id=123,
    )

    assert track.catalog_type == "external_reference"
    assert track.uploaded_by_id is None
