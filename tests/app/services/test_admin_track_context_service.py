"""Unit tests for pure helpers in admin_track_context_service."""

import pytest

from app.services.admin_track_context_service import (
    _detect_language,
    _parse_ai_response,
)


def test_detect_language_cyrillic_artist():
    assert _detect_language("Кино", "Wish You Were Here") == "ru"


def test_detect_language_cyrillic_title():
    assert _detect_language("Pink Floyd", "Группа крови") == "ru"


def test_detect_language_latin():
    assert _detect_language("The Beatles", "Yesterday") == "en"


def test_detect_language_none_values():
    assert _detect_language(None, None) == "en"


def test_detect_language_both_cyrillic():
    assert _detect_language("ДДТ", "Что такое осень") == "ru"


def test_parse_ai_response_clean_json():
    raw = '{"tracks": [{"id": 1, "content": "Hello"}]}'
    entries, err = _parse_ai_response(raw)
    assert err is None
    assert entries == [{"id": 1, "content": "Hello"}]


def test_parse_ai_response_with_preamble():
    raw = (
        "Here is the result:\n\n"
        '{"tracks": [{"id": 5, "content": "Test"}]}\n'
    )
    entries, err = _parse_ai_response(raw)
    assert err is None
    assert entries[0]["id"] == 5


def test_parse_ai_response_markdown_fences():
    raw = (
        "```json\n"
        '{"tracks": [{"id": 7, "content": "Info"}]}\n'
        "```"
    )
    entries, err = _parse_ai_response(raw)
    assert err is None
    assert entries[0]["id"] == 7


def test_parse_ai_response_garbage():
    entries, err = _parse_ai_response("not json at all")
    assert entries == []
    assert err is not None


def test_parse_ai_response_json_without_tracks_key():
    entries, err = _parse_ai_response('{"items": []}')
    assert entries == []
    assert err is not None
    assert "tracks" in err


def test_parse_ai_response_multiple_tracks():
    raw = '{"tracks": [{"id": 1, "content": "A"}, {"id": 2, "content": "B"}]}'
    entries, err = _parse_ai_response(raw)
    assert err is None
    assert len(entries) == 2
