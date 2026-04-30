from __future__ import annotations

from app.models.artist import Artist
from app.models.track import Track
from app.search.translit import transliterate


def track_playable(t: Track) -> bool:
    if t.file_key:
        return True
    return t.access_mode in ("third_party_stream", "official_embed")


def track_to_doc(t: Track) -> dict:  # type: ignore[type-arg]
    title = t.title or ""
    artist = t.artist or ""
    return {
        "track_id": t.id,
        "title": title,
        "title_sayt": title,
        "title_translit": transliterate(title),
        "artist": artist,
        "artist_sayt": artist,
        "artist_translit": transliterate(artist),
        "genre": t.genre or "",
        "play_count": int(t.play_count or 0),
        "is_active": bool(t.is_active),
        "is_public": bool(t.is_public),
        "playable": track_playable(t),
    }


def artist_to_doc(a: Artist) -> dict:  # type: ignore[type-arg]
    sc_perm = (a.soundcloud_permalink or "").strip().lower()
    name = a.name or ""
    return {
        "artist_id": a.id,
        "name": name,
        "name_sayt": name,
        "name_translit": transliterate(name),
        "name_normalized": a.name_normalized or "",
        "soundcloud_permalink": sc_perm,
    }
