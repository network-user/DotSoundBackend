"""Admin batch prompt/import for track genre and mood (LLM-assisted)."""

from __future__ import annotations

import json
import re
from typing import Any

from dotsound_private_core.services.text_genre_mood_infer import (
    normalize_genre_label,
    normalize_mood_tags,
)
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_LYRICS_EXCERPT_LEN = 900

_MOODS_ENUM = (
    "steady, bright, soft, melancholic, energetic, romantic, "
    "aggressive, calm, dark, uplifting, intimate, party, "
    "nostalgic, brooding, playful"
)

_BATCH_PROMPT = """Ты — музыкальный редактор DotSound. По фрагменту текста \
песни и метаданным определи жанр и настроение.

Правила:
— genre: одна короткая метка; язык как у текста (кириллица → русский, иначе \
английский). Пустая строка если неясно.
— moods: 0–5 тегов, только из: {moods_enum}
— Опирайся на смысл текста; title/artist — подсказки.

Ответ строго JSON:
{{
  "tracks": [
    {{"id": 123, "genre": "Поп", "moods": ["energetic", "bright"]}},
    {{"id": 456, "genre": "", "moods": []}}
  ]
}}

Список треков:
{track_list}
"""


class AdminTrackGenreMoodImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_prompt_for_tracks(
        self, track_ids: list[int]
    ) -> tuple[str, int]:
        rows = await self._load_track_lyrics_rows(track_ids)
        lines = [_format_line(t, lx) for t, lx in rows]
        prompt = _BATCH_PROMPT.format(
            moods_enum=_MOODS_ENUM,
            track_list="\n".join(lines) if lines else "(нет треков)",
        )
        return prompt, len(rows)

    async def build_prompt_for_filtered(
        self,
        *,
        search: str | None,
        only_without_genre: bool,
        limit: int,
    ) -> tuple[str, int]:
        rows = await self._load_filtered_rows(
            search=search,
            only_without_genre=only_without_genre,
            limit=limit,
        )
        lines = [_format_line(t, lx) for t, lx in rows]
        prompt = _BATCH_PROMPT.format(
            moods_enum=_MOODS_ENUM,
            track_list="\n".join(lines) if lines else "(нет треков)",
        )
        return prompt, len(lines)

    async def import_ai_response(
        self,
        *,
        raw_response: str,
        overwrite_genre: bool,
    ) -> tuple[int, list[str]]:
        entries, parse_error = _parse_ai_response(raw_response)
        if parse_error:
            return 0, [parse_error]
        imported = 0
        errors: list[str] = []
        for entry in entries:
            raw_id = entry.get("id")
            try:
                track_id = int(raw_id)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                errors.append(f"Skipped malformed entry: {entry!r}")
                continue
            track = await self._session.get(Track, track_id)
            if track is None:
                errors.append(f"track_id={track_id}: track not found")
                continue
            if not track.is_active:
                errors.append(f"track_id={track_id}: track inactive")
                continue
            g_raw = entry.get("genre")
            moods_raw = entry.get("moods", entry.get("mood_tags"))
            touched = False
            if isinstance(g_raw, str):
                g_norm = normalize_genre_label(g_raw.strip() or None)
                if g_norm and (
                    overwrite_genre
                    or not (track.genre and track.genre.strip())
                ):
                    track.genre = g_norm
                    touched = True
            moods = normalize_mood_tags(moods_raw)
            if moods:
                row = await self._session.get(
                    TrackAudioFeatures,
                    track_id,
                )
                if row is None:
                    row = TrackAudioFeatures(track_id=track_id)
                    self._session.add(row)
                existing: list[str] = []
                if row.mood_tags:
                    for x in row.mood_tags:
                        if isinstance(x, str) and x.strip():
                            existing.append(x.casefold())
                for m in moods:
                    if m not in existing:
                        existing.append(m)
                row.mood_tags = existing[:16]
                touched = True
            if touched:
                imported += 1
        if imported > 0:
            await self._session.commit()
        return imported, errors

    async def _load_track_lyrics_rows(
        self, track_ids: list[int]
    ) -> list[tuple[Track, str | None]]:
        if not track_ids:
            return []
        stmt = select(Track).where(Track.id.in_(track_ids))
        result = await self._session.execute(stmt)
        by_id = {t.id: t for t in result.scalars().all()}
        excerpts = await self._lyrics_excerpts_bulk(track_ids)
        out: list[tuple[Track, str | None]] = []
        for tid in track_ids:
            t = by_id.get(tid)
            if t is None:
                continue
            out.append((t, excerpts.get(tid)))
        return out

    def _trim_excerpt(self, plain: str) -> str:
        text = plain.strip()
        if len(text) <= _LYRICS_EXCERPT_LEN:
            return text
        return text[:_LYRICS_EXCERPT_LEN] + "…"

    async def _lyrics_excerpts_bulk(
        self, track_ids: list[int]
    ) -> dict[int, str | None]:
        if not track_ids:
            return {}
        stmt = select(
            TrackLyrics.track_id,
            TrackLyrics.plain_text,
        ).where(TrackLyrics.track_id.in_(track_ids))
        result = await self._session.execute(stmt)
        out: dict[int, str | None] = {}
        for tid, raw in result.all():
            if not raw or not str(raw).strip():
                out[int(tid)] = None
            else:
                out[int(tid)] = self._trim_excerpt(str(raw))
        return out

    async def _load_filtered_rows(
        self,
        *,
        search: str | None,
        only_without_genre: bool,
        limit: int,
    ) -> list[tuple[Track, str | None]]:
        stmt: Select[tuple[Track]] = (
            select(Track).order_by(Track.created_at.desc()).limit(limit)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        if only_without_genre:
            stmt = stmt.where((Track.genre.is_(None)) | (Track.genre == ""))
        result = await self._session.execute(stmt)
        tracks = list(result.scalars().all())
        tids = [t.id for t in tracks]
        excerpts = await self._lyrics_excerpts_bulk(tids)
        return [(t, excerpts.get(t.id)) for t in tracks]


def _format_line(track: Track, lyrics_excerpt: str | None) -> str:
    artist = track.artist or "Unknown"
    genre = track.genre or "—"
    lx = lyrics_excerpt or "(текста нет в каталоге)"
    return (
        f"— ID: {track.id} | Artist: {artist} | Title: {track.title} "
        f"| genre_now: {genre}\n  lyrics_excerpt: {lx}"
    )


def _parse_ai_response(
    raw: str,
) -> tuple[list[dict[str, Any]], str | None]:
    text = raw.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("tracks"), list):
            return data["tracks"], None
        return [], "Parsed JSON but no 'tracks' array found"
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and isinstance(
                data.get("tracks"),
                list,
            ):
                return data["tracks"], None
        except json.JSONDecodeError:
            pass
    return [], "Could not parse JSON from the provided response"
