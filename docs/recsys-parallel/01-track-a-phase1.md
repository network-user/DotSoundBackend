# Чат A — Phase 1: genre preview onboarding

## Корень workspace

`C:\Users\User\PycharmProjects\DotSoundBackend`

Не открывать в этом чате: `DotSoundPrivateCore`, `DotSoundComputeWorker`, `DotSoundBot`.

## Цель

Онбординг с **15-сек превью по жанру**: гибрид курируемых `genre_samples` + добор по `play_count`, только треки с `blob_id` (прокси-источники без blob — исключить). Админ может наполнять кураторский список.

## Уже сделано в репо

- Миграция Alembic: `alembic/versions/0059_genre_samples_and_preview_clips.py`  
Таблицы: `genre_samples` (genre, track_id, position, curated, …), `track_preview_clips` (PK track_id, start_sec, duration_sec, source ∈ fixed_offset|content_based).

## Декомпозиция (порядок внутри чата)

1. **ORM:** `app/models/genre_sample.py`, `app/models/track_preview_clip.py` — по стилю `app/models/compute_job.py`; зарегистрировать в `app/models/__init__.py`.
2. **Репозиторий/сервис:** `app/services/genre_samples_service.py` (async, `AsyncSession`):
  - `get_preview_queue(genre, limit)` — курируемые по position, затем добор из `TrackRepository` по play_count, фильтры `blob_id IS NOT NULL`, `is_active`, `duration_seconds IS NOT NULL`.
  - `ensure_preview_clip(track_id)` — upsert клипа: старт по умолчанию из длительности трека, длительность min(15, остаток).
  - `add_curated` / `remove_curated` / `list_curated` для админа.
3. **Схемы:** `app/schemas/genre_samples.py` — DTO очереди и админ create.
4. **API публичный:** расширить `app/api/v1/onboarding.py` — например
  `GET /onboarding/genres/{genre}/preview-queue?limit=10` (префикс роутера как у существующих onboarding).
5. **Превью аудио:** новый модуль `app/api/v1/track_preview.py` (или включение в `tracks` router без дублирования playback):
  - `GET` сегмента (контейнер **MP4** + **AAC**, `Content-Type: audio/mp4`, fragmented output, `Cache-Control: public, max-age=86400`).
  - Источник: presigned URL как в `app/api/v1/tracks/playback.py` + `ensure_preview_clip`; ffmpeg subprocess; timeout и cleanup (см. идеи в `app/services/snippet_worker.py` / snippet pipeline).
  - Для обычных пользователей не принимать произвольные start/duration из query (защита от перебора).
6. **Админ:** `app/api/v1/admin/genre_samples.py` — CRUD/list; **новая** capability в `app/services/admin_manifest_service.py`, например `recsys.genre_samples.manage` (меню по желанию); `require_capability(...)`; подключить в `app/api/v1/admin/__init__.py`.
7. **Роутер:** `app/api/router.py` — включить track_preview и admin genre_samples.
8. **Frontend:** `frontend/src/components/Onboarding/OnboardingGenreScreen.tsx`, `frontend/src/hooks/usePreviewQueue.ts`; в `Onboarding.tsx` шаг genres рендерит экран; `frontend/src/lib/api.ts` — `fetchGenrePreviewQueue`.
9. **Тесты:**
  `tests/app/services/test_genre_samples_service.py`  
   `tests/app/api/v1/test_onboarding_preview.py`  
   `tests/app/api/v1/test_track_preview.py`  
   `tests/app/api/v1/test_admin_genre_samples.py`

## Коммит (одна строка)

```
feat(onboarding): add hybrid genre samples with 15s preview queue
```

## Pytest (одна строка)

```
pytest -q tests/app/services/test_genre_samples_service.py tests/app/api/v1/test_onboarding_preview.py tests/app/api/v1/test_track_preview.py tests/app/api/v1/test_admin_genre_samples.py
```

## Промпт для вставки в новый чат

```
Открой полный контекст: C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\01-track-a-phase1.md
Workspace только DotSoundBackend. Реализуй Phase 1 по декомпозиции в этом файле. Соблюдай AGENTS.md и CLAUDE.md; .env не читать; DotSoundBot не трогать. После зелёных тестов — один коммит с сообщением из файла; обнови TODO.md.
```

## Конфликты с другими чатами

Этот чат **единолично** владеет `DotSoundBackend` для своей ветки. Не запускай параллельно второй чат на тот же репозиторий/ветку. Параллельно безопасен только **чат B-pre** (другой репо — PrivateCore).

---

## После успеха всего recsys-спринта

Когда выполнены **все** треки (A, B-pre, B1, B2) и они влиты: удали каталог `docs/recsys-parallel/` и секцию в `docs/project_context.md` — см. [README.md](README.md) раздел «Уборка».