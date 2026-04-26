# DotSound — Project Context (auto-generated 2026-04-16, обновлено 2026-04-24)

> Открывать при каждом новом сеансе. Обновлять при архитектурных изменениях.

---

## Что такое DotSound

Музыкальная платформа в стиле Telegram: открытый клиент (Backend) + закрытая логика (PrivateCore).
Пользователи загружают треки, слушают, ставят лайки, общаются в чатах, видят текст песни с таймкодами.

---

## Четыре репозитория


| Репо                      | Путь                                                  | Роль                                                                                                                                                    |
| ------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DotSoundBackend**       | `C:\Users\User\PycharmProjects\DotSoundBackend`       | FastAPI + React + PostgreSQL + Redis + MinIO; опционально **Elasticsearch 8** для полнотекстового поиска и suggest. Hub: оркестрация, БД, очередь jobs. |
| **DotSoundBot**           | `C:\Users\User\PycharmProjects\DotSoundBot`           | Telegram-бот (aiogram 3). Только UI.                                                                                                                    |
| **DotSoundPrivateCore**   | `C:\Users\User\PycharmProjects\DotSoundPrivateCore`   | Чистый Python, без фреймворков. Алгоритмы, константы, политики.                                                                                         |
| **DotSoundComputeWorker** | `C:\Users\User\PycharmProjects\DotSoundComputeWorker` | Pull-based ASR-воркер (faster-whisper + опциональный Demucs). Дёргает Backend по HMAC, делает тяжёлый compute, отдаёт результат.                        |


**Правила:**

- Backend импортирует из PrivateCore. PrivateCore ничего не знает о FastAPI/SQLAlchemy.
- Worker импортирует из PrivateCore. Backend никогда не загружает faster-whisper в свой процесс — `disable_local_asr=True` плюс отсутствие `ml`-extra гарантируют это.

---

## Стек Backend

- **API:** FastAPI (Python 3.12), async/await
- **БД:** PostgreSQL 14+, SQLAlchemy 2.x async, Alembic миграции
- **Очередь:** Redis + Taskiq (воркеры: transcoding, lyrics, cover, import, ES reindex)
- **Поиск (опц.):** Elasticsearch 8 (`elasticsearch` PyPI, async), индексы `dotsound_tracks` / `dotsound_artists`; при пустом `ELASTICSEARCH_URL` — только PostgreSQL
- **Хранилище:** MinIO (S3-совместимый)
- **Исходящий Tor (опц.):** по умолчанию выкл. (`TOR_POOL_ENABLED` в `.env`); пул SOCKS в `app.services.tor_pool` для отдельных внешних API (см. `.env.example`)
- **Аутентификация:** JWT + Telegram HMAC + Email (magic link) + TOTP 2FA
- **Real-time:** WebSocket (Redis Pub/Sub), присутствие, typing indicators
- **Фронтенд:** React 18 + TypeScript + Vite, CSS custom properties (без Tailwind)
- **Состояние:** PlayerContext (Zustand-like), LikesContext, lyricsTaskStore

---

## Ключевые директории Backend

```
app/
  api/v1/          ← роуты (НЕ содержат DB-запросов напрямую)
  services/        ← бизнес-логика
  search/          ← ES: AsyncElasticsearch, маппинги индексов, документы; не тянет ORM в слой запроса
  repositories/    ← DB-запросы
  models/          ← SQLAlchemy модели
  schemas/         ← Pydantic схемы
  core/            ← db, auth, s3, ws_manager, taskiq broker, observability (в т.ч. метрика ES)
frontend/src/
  components/      ← UI компоненты
  views/           ← страницы (Home, Search, Upload, ...)
  store/           ← PlayerContext, LikesContext, lyricsTaskStore
  lib/api.ts       ← ВСЕ API-вызовы (1226 строк)
  lib/ws.ts        ← WebSocket с авто-реконнектом
```

---

## Поиск: Elasticsearch (опционально)

Полнотекстовый поиск треков по `q` и **autocomplete** (треки + артисты каталога) вынесены
в отдельный кластер ES, чтобы не нагружать PostgreSQL `ILIKE` на больших каталогах.
Источником истины остаётся БД: индексы **event-driven** (Taskiq после мутаций трека/артиста,
импорты, транскод и т.д.).

- **Инфра:** сервис `elasticsearch:8.12` в `docker-compose.yml`, volume, healthcheck;
backend/worker получают `ELASTICSEARCH_URL` (в контейнерах — `http://elasticsearch:9200`,
с хоста — `http://localhost:9200`).
- **Код:** `app/search/` — клиент, создание индексов, поля `search_as_you_type` для
bool-prefix suggest; `search_query_service` (поиск/suggest), `search_index_service` (index/delete,
backfill). `TrackService.search` и discovery при доступном ES сначала берут id из ES,
затем **гидратацию** из PostgreSQL (`get_by_ids_preserve_order`); иначе — SQL как раньше
(метрика `pg_fallback`). Список артистов с `q` при необходимости согласован с ES
в `ArtistService` / discovery.
- **Taskiq** (`app.services.search_index_worker`, подключён вместе с остальными): `reindex_track_task`,
`reindex_artist_task` (и связанные треки), `delete_track_es_task`, `reindex_backfill_all_task`.
Старт воркера: `ensure` индексов при доступном кластере.
- **Play count:** краткосрочные всплески проигрываний копятся в Redis; фоновый
`playcount_drain_loop` в lifespan периодически пишет в PG и **батчит** обновление
`play_count` в ES для «грязных» id.
- **API:** `GET /api/v1/search/suggest` (rate limit), публичный трек-листинг с текстовым
`q` использует тот же поисковый путь. В `DEBUG` может быть `GET /api/v1/search/_admin/reindex`
для ручного backfill.
- **Наблюдаемость:** counter `elasticsearch_query_total{op, outcome}` — в т.ч. `track_search`
(`es_ok`, `pg_fallback`) и `suggest` (`es_ok`, `es_fail`, `es_error`).

Подробные переменные: `elasticsearch_url`, `elasticsearch_enabled`, имена индексов,
`elasticsearch_backfill_on_empty`, `elasticsearch_dev_bootstrap`,
`elasticsearch_track_fuzziness`, `elasticsearch_fuzzy_max_expansions` — в `app/config.py` и `.env.example`.

---

## Ключевые директории PrivateCore

```
src/dotsound_private_core/
  contracts/internal_api.py   ← константы внутреннего API
  services/
    lyrics_provider.py        ← автоопределение текста (внутренняя реализация)
    artist_normalizer.py      ← парсинг "Kai Angel & 9mice", fuzzy match
    recommendation_engine.py  ← скоринг треков, daily mix, radio
    auth_policy.py            ← TTL, IP-диапазоны, burn/cooldown
    upload_policy.py          ← разрешённые MIME, опасные расширения
    abuse.py                  ← disposable email, Tor exit nodes
    scoring.py                ← веса сигналов, maturity levels
    cold_start.py             ← onboarding, калибровка
    moderation.py             ← порог авто-скрытия
    account_deletion_policy.py← grace period 30 дней
```

---

## Lyrics — каскадная модель (после rev 0044)

Backend = чистый hub. Каждая задача попадает в `LyricsJob` с
полем `tiers_planned` (по умолчанию: `catalog_only`,
`remote_whisper`, `speechkit_paid`) и `current_tier`.
`tier_attempts` JSONB хранит лог каждой попытки с
`{tier, started_at, status, error, finished_at}`.

1. Пользователь нажимает "Авто-генерация" → `LyricsService.trigger_auto_generation`
2. `lyrics_cascade.start_cascade` создаёт job, ставит первый tier:
  - `**catalog_only**` — Backend Taskiq, вызывает
  - `**remote_whisper**` — Backend оставляет job со статусом
  `queued, profile=gpu_full`. Удалённый
  `DotSoundComputeWorker` забирает через HMAC pull API
  (`/api/v1/internal/audio-compute/jobs/claim`).
  - `**speechkit_paid**` — Backend дёргает Yandex Cloud
  SpeechKit Async через `asr_speechkit_adapter.transcribe`.
  Tier выключен по умолчанию + жёсткий бюджет-гард
  (`asr_policy.should_use_paid_asr`).
3. Tier-успех → `LyricsRepository.create_or_update`, job → `done`.
4. Tier-фейл / lease expired (lease reaper) →
  `lyrics_cascade.handle_tier_failure` → следующий tier.
5. Cascade exhausted → `status="failed"`, причина в `error`.

Whisper (faster-whisper / Demucs) **никогда** не выполняется в
Backend-процессе. Если хочется быстрый dev-loop без поднятия
отдельного Worker'а — флаг `LYRICS_ALLOW_LOCAL_ASR=true` в `.env`
(валидатор в `app/config.py` запрещает его в проде).

См. также:

- `app/services/lyrics_cascade.py` — единственный авторитет на
переходы между tier'ами.
- `app/services/lyrics_worker.py` — `catalog_only_lyrics_task`
и `speechkit_lyrics_task`.
- `app/api/v1/internal/audio_compute.py` — HMAC API для
удалённого воркера.
- `app/middlewares/internal_api_allowlist.py` — IP allowlist
для `/api/v1/internal/`*.
- `docs/compute-worker-protocol.md` — публичный контракт
HMAC + claim/result для воркера.

Всё, что относится к источникам текста, распознаванию и
сопоставлению — внутренняя реализация PrivateCore и в этом
документе не описывается.

### Observability

- Все события воркера дублируются в Redis Stream
`worker_events:{worker_id}` (MAXLEN ~ 1000); админ-WS канал
`worker_logs:{worker_id}` стримит их в реальном времени.
- Полный таймлайн job'а доступен по WS-каналу `job_trace:{job_id}`
(источник: `LyricsJob.tier_attempts` + `WorkerAuditLog`).
- Prometheus-метрики: `lyrics_jobs_total`, `lyrics_job_duration_seconds`,
`tier_fallback_total`, `worker_anomaly_total`,
`hmac_auth_failures_total`, `speechkit_spent_rub_total`,
`speechkit_budget_remaining_rub`, `worker_heartbeat_lag_seconds`,
`elasticsearch_query_total` (op/outcome, если ES включён).

### Security (compute pipeline)

- HMAC-SHA256 по канону `METHOD\nPATH\nTS\nNONCE\nSHA256(BODY)`,
ключ = `sha256(raw_secret)`. Skew ±60s, nonce dedup в Redis 5
min.
- Per-worker IP allowlist (`ComputeWorker.allowed_ip_cidrs`,
`dotsound_private_core.services.network_policy`).
- Per-action rate limit (slowapi-style через Redis), 3 нарушения
в 10 min → auto-suspend на 5 min.
- Anomaly detector: `processing_too_fast`, `duplicate_result`,
`suspicious_failure_rate`, `stale_after_claim`. 3 флага в час
→ auto-suspend на 30 min + admin alert.
- OTT для скачивания аудио: TTL 5 min, привязан к
`worker.last_ip`, single-use через Redis `SET NX EX`.

---

## Известные проблемы (актуально на 2026-04-16)


| #   | Проблема                                                        | Файл                                | Приоритет  |
| --- | --------------------------------------------------------------- | ----------------------------------- | ---------- |
| 1   | Avatar upload заморожен (hardcode 501)                          | `app/api/v1/users.py`               | 🔴 Высокий |
| 2   | WS handlers не отписываются → утечка памяти                     | `frontend/src/lib/ws.ts`            | 🔴 Высокий |
| 3   | play_count в ответе — устаревшее значение                       | `app/api/v1/tracks/playback.py`     | 🟠 Средний |
| 4   | Race condition на счётчике жалоб                                | `app/services/complaint_service.py` | 🟠 Средний |
| 5   | `.catch(() => {})` везде — пользователь не видит ошибки         | Много компонентов фронта            | 🟠 Средний |
| 6   | "error" vs "not_found" в lyrics generation не различаются в UI  | `lyricsTaskStore.ts`                | 🟠 Средний |
| 7   | Нет аудита admin-действий                                       | `app/api/v1/admin/`                 | 🟡 Низкий  |
| 8   | Нет ротации ключей шифрования чата                              | `message_service.py`                | 🟡 Низкий  |
| 9   | Grace period при удалении аккаунта не показывается пользователю | `users.py` + frontend               | 🟡 Низкий  |


---

## Модели данных (ключевые)


| Модель        | Особенности                                                                          |
| ------------- | ------------------------------------------------------------------------------------ |
| `User`        | telegram_id ИЛИ email обязательны (CHECK constraint). `deleted_at` = мягкое удаление |
| `Track`       | `processing_status`, `source` (internal/soundcloud), `access_mode`. HLS ключи в S3   |
| `TrackLyrics` | 1:1 с Track. `synced_lines` JSONB = `[{time_ms, text}]`. `source` = manual/auto      |
| `Message`     | `content` зашифрован ChaCha20                                                        |
| `ImportJob`   | Статус bulk-импорта из Telegram/SoundCloud                                           |


---

## Auth flow

```
Telegram WebApp initData → HMAC verify → JWT (7 дней)
Email magic link → Resend API → verify token → JWT
2FA TOTP → TOTP verify → JWT
Internal services → scoped JWT (15 мин) + IP whitelist
```

---

## Фоновые задачи (Taskiq)


| Задача                       | Триггер                                                     |
| ---------------------------- | ----------------------------------------------------------- |
| `transcode_audio`            | После загрузки трека                                        |
| `transcode_video`            | После загрузки видео                                        |
| `generate_and_upload_cover`  | Нет обложки                                                 |
| `generate_lyrics_task`       | Кнопка авто-генерации                                       |
| `generate_lyrics_debug_task` | Debug UI (изолированный запуск отдельной стадии провайдера) |
| `import_soundcloud_track`    | Импорт по URL                                               |
| `import_telegram_profile`    | Сканирование профиля бота                                   |
| `reindex_track_task`         | Изменения трека, импорт, транскод, постановка из сервисов   |
| `reindex_artist_task`        | Создание/обогащение артиста                                 |
| `delete_track_es_task`       | Удаление трека из индекса                                   |
| `reindex_backfill_all_task`  | Полный backfill (также с lifespan при флагах)               |


---

## ENV переменные (критические)


| Переменная              | Где используется                                                             |
| ----------------------- | ---------------------------------------------------------------------------- |
| `JWT_SECRET`            | Backend: подпись JWT                                                         |
| `TELEGRAM_BOT_TOKEN`    | Backend: верификация Telegram HMAC                                           |
| `RESEND_API_KEY`        | Backend: отправка email                                                      |
| `TOTP_ENCRYPTION_KEY`   | Backend: шифрование TOTP secret                                              |
| `CHAT_ENCRYPTION_KEY`   | Backend: шифрование сообщений                                                |
| `DEBUG`                 | Backend: разрешает mock auth и debug endpoints                               |
| `ELASTICSEARCH_URL`     | Пусто — поиск/suggest только через PG; в Docker: `http://elasticsearch:9200` |
| `ELASTICSEARCH_ENABLED` | `true`/`false` — мастер-флаг; при `false` клиент не используется             |


Остальные: `ELASTICSEARCH_INDEX_*`, `ELASTICSEARCH_BACKFILL_ON_EMPTY`,
`ELASTICSEARCH_DEV_BOOTSTRAP`, `ELASTICSEARCH_PLAYCOUNT_FLUSH_INTERVAL_SECONDS` —
см. `app/config.py` и `.env.example`.

Переменные окружения, относящиеся к PrivateCore, описаны внутри
самого PrivateCore (см. `DotSoundPrivateCore/.env.example`) и здесь
не дублируются по правилу чёрного ящика.

---

## Продуктовые эндпоинты (радио, co-listen, автор-аналитика, коллаб, сниппеты)

Публичный API дополнен: «радио-очередь» от сида, комнаты co-listen с
WebSocket на Redis, статистика для владельца трека, приглашения в
со-редакторы плейлиста и фоновые сниппеты UGC. Схема БД — миграция
`0056_*`; политики лимитов в `DotSoundPrivateCore` (`radio_policy`,
`colisten_policy`, `author_stats_policy`, `playlist_collab_policy`,
`snippet_policy`).

---

## Стиль кода

- Python: Black (79 chars), Ruff, MyPy strict
- TypeScript: CSS custom properties, без Tailwind
- Архитектура: `api/v1/` → `services/` → `repositories/` → `models/`
- Правило: route handlers не делают DB-запросы напрямую
- Правило: security constants только из PrivateCore

---

## Документы политик

- `docs/ai-boundary-policy.md` — что идёт в PrivateCore, что в Backend
- `DotSoundPrivateCore/docs/ai-boundary-policy.md` — то же с примерами
- `DotSoundPrivateCore/agents.md` — правила для AI-агентов в PrivateCore
- `DotSoundBackend/agents.md` — правила для AI-агентов в Backend

