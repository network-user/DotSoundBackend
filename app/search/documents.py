from __future__ import annotations

from app.models.artist import Artist
from app.models.track import Track


def track_playable(t: Track) -> bool:
    if t.file_key:
        return True
    return t.access_mode in ("third_party_stream", "official_embed")


def track_to_doc(t: Track) -> dict:
    return {
        "track_id": t.id,
        "title": t.title or "",
        "title_sayt": t.title or "",
        "artist": t.artist or "",
        "artist_sayt": t.artist or "",
        "genre": t.genre or "",
        "play_count": int(t.play_count or 0),
        "is_active": bool(t.is_active),
        "is_public": bool(t.is_public),
        "playable": track_playable(t),
    }


def artist_to_doc(a: Artist) -> dict:
    return {
        "artist_id": a.id,
        "name": a.name or "",
        "name_sayt": a.name or "",
        "name_normalized": a.name_normalized or "",
    }
