from app.services.bandcamp_service import _bc_search_from_html


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
