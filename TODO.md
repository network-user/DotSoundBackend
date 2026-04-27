# DotSound — TODO Tracker

> Этот файл поддерживается автоматически ИИ-агентом.
> Агент обязан: (1) прочитать этот файл в начале сессии,
> (2) обновить статусы после выполнения задач,
> (3) добавить новые задачи если они возникли.

## Статусы

- `[ ]` — не начато
- `[~]` — в процессе
- `[x]` — завершено
- `[-]` — отменено / неактуально

---

## Соответствие 152-ФЗ / ПДн (backlog, продукт + инженерия)

- [ ] Перед публичным запуском: **согласовать с юристом/ДПО** фактическую
  обработку ПДн с требованиями 152-ФЗ (и смежное): основания, при
  необходимости уведомительный/регистрационный контур, субпроцессоры
  (email, observability, ASR-облака, бэкапы), трансгран, сроки хранения,
  запросы субъектов, реагирование на инциденты. Опора на `LEGAL.md`,
  `docs/legal/PRIVACY_POLICY.md` (сейчас draft).
- [ ] **Скорректировать функционал** по итогам: ретеншн/удаление,
  минимизация полей, kill-switch внешних API, согласованность логов и
  бэкапов с политикой. Не полагаться на внутренние id вместо
  `telegram_id` как на «анонимизацию», устраняющую операторские
  обязанности.
- См. также: `docs/project_context.md` (compliance), `AGENTS.md` (Legal
  readiness).

## Критичные / Инфраструктура

- Система бэкапов: PostgreSQL + Redis + configs (локально)
- Система логирования: JSON structlog + Docker log rotation
  (тонкая настройка: `REDACT_LOGS`, `REDACT_LOG_IDENTIFIERS`, `LOG_THIRD_PARTY_LEVEL`)
- Outbound Tor pool: по умолчанию выкл., `TOR_POOL_ENABLED=true` — opt-in
- [x] Taskiq worker: graceful shutdown (`WORKER_SHUTDOWN`: cancel
  `import_queue_dispatcher` / `lyrics_global_orchestrator` background tasks,
  `close_es` в воркере) — 2026-04
- [x] Docker Compose `worker` service: taskiq modules aligned with
  root `main.py` (imports, lyrics queue, snippets) — 2026-04
- [x] Audio-compute worker download: OTT with `proxy=1` so Backend
  proxies SoundCloud progressive streams (worker no longer GETs
  time-bound CDN URL directly; avoids 403) — 2026-04
- [x] Lyrics cascade: preserve **root** worker failure in
  `cascade exhausted` message (not only last tier gate, e.g.
  `speechkit_disabled`); `lyrics_jobs.request_with_sync` /
  `request_bypass_cache` for fallback dispatch; log
  `audio_compute_worker_fail` — 2026-04
- **Полное копирование аудиофайлов (MinIO) на удалённый backup-VPS**
  - Подключение к отдельному серверу по SSH
  - `mc mirror` MinIO -> remote, инкрементально
  - Шифрование трафика, ключевая аутентификация
  - Настройка через `.env` (`BACKUP_REMOTE_HOST`)
  - UI в админ-панели: запуск/статус/расписание бэкапа
- Админ-панель (frontend): раздел управления бэкапами
  - Просмотр списка бэкапов, размеры, даты
  - Ручной запуск полного бэкапа
  - Настройка расписания
  - Статус последнего бэкапа (OK / FAIL)
  - Кнопка восстановления (с подтверждением)

## Админ-панель (выполнено)

- **Полноценная админ-панель** (Phase 1-5)
  - Backend `/api/v1/admin/*`: auth (TOTP onboarding с QR, login,
  device approval, step-up, refresh, logout), dashboard,
  tracks/users/complaints (без inline SQL), tasks (lyrics_jobs +
  Taskiq queues + worker audit), logs (Loki proxy), metrics
  (Prometheus proxy), system (services health, containers,
  migrations, feature flags на app_settings), audit
  (admin_actions_log + CSV export), security (login attempts,
  locked users, lockout release), WebSocket для realtime
  - Многоуровневая защита: admin TOTP + device binding +
  pending_device email-flow + step-up для критичных действий +
  Telegram-алерты + короткие 15-мин сессии + rotating refresh +
  CSRF double-submit + строгий CSP + brute-force lockout
  - Observability: Prometheus + Grafana + Loki + Tempo +
  cAdvisor через `docker-compose.observability.yml`,
  `app/core/observability.py` (metrics/tracing/Sentry с PII-фильтром),
  расширенный `/health/deep` (db/redis/s3/taskiq/loki/prometheus)
  - Frontend `frontend/src/admin/` как chunked secure bundle:
  AdminApp, routes, layout, recharts графики, TanStack
  Query/Table, Zustand stores, semantic state-tokens только
  для StatusPill (см. design-system.md)
  - Документация: `docs/admin/{README,security,onboarding,testing,nginx-example.conf}`
- UX (2026-04): `AdminPromptProvider` (модалки вместо `alert`/`confirm`),
  i18n для строк админки, динамический заголовок раздела в topbar,
  выдвижное меню на «узком» вьюпорте (≤720px), сортировка колонок
  в `DataTable` на Users/Tracks/Tasks/Artists/queues
- Перенести admin-security policy в PrivateCore (см. выше)
- WebAuthn/Passkey как опциональный второй фактор

## Безопасность

- Scoped JWT для internal-token (bot_player, 15 мин TTL)
- IP whitelist + rate limit на internal endpoints
- hmac.compare_digest для secret comparison
- Аудио sanitization через FFmpeg перекодирование (payload уничтожается)
- Аудит-лог входов через бота (расширить login_history)
- Rate limit тюнинг под production нагрузку
- **Глубокая валидация загрузок (Layer 1)**
  - `python-magic-bin` для проверки magic bytes (`file_validator.py`)
  - Интеграция в audio upload, cover upload, video upload
  - Запрет двойных расширений (`.exe`, `.bat`, `.cmd` и др.)
- **Sanitization изображений (Layer 2)**
  - Pillow re-encode для обложек и аватаров (через `media_service.process_image`)
- [~] **Сканирование загрузок: режим `lightweight` ИЛИ `clamav`**
  - Конфиг `upload_malware_scan_mode: none | lightweight | clamav` в `config.py`
  - `scan_service.py` stub (ScanResult, scan_bytes)
  - Документировано в `.env.example` с рекомендациями по VPS
  - Реализация `lightweight` режима (YARA + эвристики, PrivateCore)
  - Реализация `clamav` режима (clamd TCP/socket, quarantine flow)
  - Разделить слои: сигнатуры/эвристики/пороги в PrivateCore, clamd/quarantine orchestration в Backend
- **CSP и изоляция (Layer 4)**
  - `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff` на все ответы
  - `Content-Security-Policy: default-src 'none'` на медиа-ответы

## Граница Backend / PrivateCore

- [x] **Плейлист «Выбор пользователей» + учёт `play_count` (2026-04-27):**
  PrivateCore `playcount_policy` (qualify, `rank_user_choice_tracks`);
  `GET /api/v1/recommendations/user-choice`, секция `user_choice` в
  `GET /api/v1/recommendations/home`; `PublicPlayCountService` + Redis
  24h-дедуп; залогиненные — сигнал listen; гость — `POST /api/v1/tracks/{id}/play`
- [x] **Рекомендации (2026-04):** приоритет русскоязычного контента —
  `recommendation_language_policy` (PrivateCore), affiniti из истории
  + `users.locale`, стратификация пула кандидатов, RU-запросы в
  external discovery; см. `docs/project_context.md`,
  `docs/private-boundary-inventory.md`
- [x] **Recsys — Track A / Phase 1 (2026-04):** гибрид
  `genre_samples` + очередь 15s превью, `GET .../preview-queue`,
  track-preview сегмент, админ-CRUD и capability
  `recsys.genre_samples.manage`
- [x] **Recsys — Track B1 / Phase 5 Backend (2026-04):**
  миграция `0060` (таблицы features/similarity), internal API
  `/api/v1/internal/compute/*` (HMAC), `compute_results_router`,
  post-upload enqueue, CLI `python -m app.cli.compute_backfill`,
  `track_features_builder` + тесты
- [x] **Recsys handoff (2026-04-27):** удалён каталог
  `docs/recsys-parallel/`; ссылка в `project_context` убрана; тест
  `test_backfill_dry_run_uses_patched_session` чинит патч
  `AsyncSessionLocal` в `app.cli.compute_backfill`
- **Immediate: перенести auth/email policy в PrivateCore**
  - `account_linking_service`: `_LINK_TTL`, `_LINK_EMAIL_TYPE`, `_LINK_PREFIX`, `_LINK_TG_PREFIX`
  - `account_linking_service`: импортировать `is_disposable_email` из `dotsound_private_core.services.abuse`
  - `email_auth_service`: `_2FA_SESSION_TTL`, `_MAGIC_LINK_TYPE`, `_2FA_SESSION_TYPE`, `_ML_PREFIX`
  - `email_auth_service`: policy генерации fallback OTP (6-значный код) перенести в helper PrivateCore
  - `email_sender`: текст TTL fallback-кода строить от `FALLBACK_CODE_TTL`, без hardcoded `5 minutes`
- **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - Перенесён inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` доступны через `AdminRepository`/admin endpoints
- **Перенести admin-security policy в PrivateCore**
  - Создан `dotsound_private_core/services/admin_security_policy.py`
  с константами и decision-функциями
  - Удалён временный stub `app/core/_admin_security_constants.py`
  - Все backend модули (admin_auth_service, admin_device_service,
  admin_alert_service, admin_manifest_service, ws.py, observability.py)
  переключены на импорт из PrivateCore
  - Добавлен endpoint-контракт `ADMIN_ALERT_ENDPOINT` в
  `dotsound_private_core/contracts/internal_api.py` + URL builder
  `admin_alert_url` в `internal_bridge.py`
  - Реализован `handle_admin_alert` в DotSoundBot
  (`bot/api/internal.py`) с allowlist `chat_id` и HTML-escape
  - Тесты: PrivateCore 88 admin-related, Bot 9 admin alert,
  Backend smoke + repo

## Продукт: пять спринтов (реализовано в Backend, 2026-04)

- [x] S1 **Radio** — `GET /api/v1/tracks/{id}/radio` (каталог + YouTube mix/search + materialize), флаги `RADIO_*` в `config`, политика `dotsound_private_core.services.radio_policy`
- [x] S2 **Co-listen** — `co_listen_rooms` + `POST/GET/PATCH /api/v1/colisten/rooms`, `WS /api/v1/colisten/ws/{room_id}` (Redis pub/sub), `dotsound_private_core.services.colisten_policy`
- [x] S3 **Author stats** — `GET /api/v1/tracks/{id}/author-stats` (владелец), `listen_events` + `play_count` + лайки, `author_stats_policy` (округление)
- [x] S4 **Плейлисты коллаб** — `playlist_collaborators`, `playlist_invite_tokens`, `POST /playlists/{id}/invites`, `POST /playlists/invites/accept`, правка `PlaylistService` для **editor** коллаб
- [x] S5 **Сниппеты** — `track_snippets`, `POST /tracks/{id}/snippets`, `snippet_worker` (Taskiq + ffmpeg), `snippet_policy` + gating `catalog_type`
- [ ] **Follow-up:** Mini App / бот (кнопки radio, colisten, UI статистики, accept invite), e2e-тесты, Prometheus-метрики `radio_*` / runbook; юридический sign-off third-party + сниппетов (см. `LEGAL.md`). Миграция: `alembic upgrade 0056`.

## Плеер в боте

- Inline аудио-плеер (3 трека, editMessageMedia)
- Выбор источника: Мои / Лайки / Лента
- file_id кэш в Redis
- Предзагрузка следующей пачки
- Фильтрация треков без файлов (playable_only)
- Расширить источники: плейлисты, подписки, рекомендации
  - Для источника "рекомендации": алгоритм ранжирования и скоринг в PrivateCore, Backend/бот — адаптеры выдачи
- Shuffle / Random режим

## Интернационализация (i18n)

- **Английская версия сайта (базовая)**
  - `react-i18next` + `i18next-browser-languagedetector`
  - JSON-каталоги `ru.json` / `en.json` (ключевые экраны: Auth, Home, Nav, Search, Liked, Upload, Profile, Playlists, Settings)
  - Telegram `language_code` custom detector
  - Переключатель языка в SettingsSheet
  - Поле `locale` в модели User + PATCH /users/me
  - Alembic миграция `0024`
- i18n: мигрировать оставшиеся ~35 .tsx файлов на `useTranslation`

## Эквалайзер

- 8-полосный Web Audio EQ (32 Hz -- 16 kHz)
- Preset-система
- Серверная синхронизация настроек (`GET/PUT /api/v1/users/me/eq`)
- **Улучшения эквалайзера (v2)**
  - Параметрический Q-factor (ширина полосы) на каждой полосе
  - Визуализация АЧХ в реальном времени (canvas/SVG)
  - Дополнительные пресеты: Bass Boost, Vocal, Classical, Electronic
- **Продвинутая обработка (v3)**
  - Compressor/Limiter (`DynamicsCompressorNode`)
  - Stereo Balance / Pan
  - Loudness normalization

## PWA / Фоновый плеер

- [x] Установка на устройство: `isTelegram()` по `initData` / user; `InstallPrompt` (iOS Safari / прочий iOS, Chromium `beforeinstallprompt`, fallback без BIP); manifest `id`, один `link` manifest
- Media Session API (lock-screen контроли: play/pause/next/prev/seekto)
- Браузерная версия с email auth + Telegram code auth
- **PWA-слой поверх текущего SPA**
  - `manifest.json` через `vite-plugin-pwa` (name, icons SVG, standalone, theme_color)
  - Service Worker: `NetworkFirst` для API, `CacheFirst` для статики
  - Иконки: 192x192 и 512x512 SVG в `frontend/public/`
  - Meta-теги: theme-color, apple-touch-icon, apple-mobile-web-app-capable
- Picture-in-Picture для видео-треков
  - `video.requestPictureInPicture()` в `TrackCardSheet.tsx`
- **Offline-кэш треков (сохранение для оффлайн-прослушивания)**
  - **Сохранение**: кнопка "Скачать" на TrackCardSheet; аудио кешируется в Cache API (`caches.open('offline-tracks')`)
  - **Хранилище**: IndexedDB для метаданных (track JSON, обложка blob, статус); Cache API для аудиофайлов
  - **Управление**: экран "Скачанные" (список, занято места, кнопка удаления); лимит по объёму (настраиваемый, ~500MB)
  - **Оффлайн-режим**: Service Worker перехватывает `/api/v1/tracks/{id}/audio` и `/hls/` — если есть в кеше, отдаёт локально
  - **Плеер**: `playTrack()` проверяет Cache API перед сетевым запросом; оффлайн-треки играют без интернета
  - **Синхронизация**: при появлении сети — sync play counts (Background Sync API); обновление метаданных
  - **Ограничения**: HLS-треки кешировать как один файл через fallback endpoint `/audio`; DRM/лицензирование не применяется (UGC-платформа)
- **Грамотный единый плеер для разных платформ / источников**
  - Привести к единому UX `ugc`, `licensed`, `external_reference`
  - Разделить `access_mode`: `internal_stream`, `third_party_stream`, `official_embed`, `external_link`
  - Показать пользователю понятный режим доступа: наш стрим / внешний поток / открыть источник
  - Для каждого источника определить допустимую механику playback и ограничения по Terms
  - Гармонизировать `PlayerContext`, `TrackCard`, `TrackCardSheet`, deep links и search/import UX
  - Не смешивать в UI внешний reference и внутренний storage-backed трек как один и тот же тип воспроизведения

## Видео к трекам

- Загрузка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- Удаление видео (`DELETE /tracks/{id}/video`)
- Отдача видео (`GET /tracks/{id}/video`, proxy из S3)
- UI: фоновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- **Оптимизация/сжатие видео**
  - Taskiq task `transcode_video` (`video_transcoding.py`): FFmpeg H.264 + AAC
  - Max 720p, CRF 23, `-preset medium`, `-movflags +faststart`
  - Thumbnail генерация (FFmpeg `-ss 1 -frames:v 1`)
  - `video_processing_status` + `video_thumbnail_key` на Track (миграция `0023`)
  - Upload -> temp S3 -> queue -> async transcode -> update status
- Увеличить лимит загрузки до 50MB (из PrivateCore `MAX_VIDEO_BYTES`)
- Адаптивный HLS для видео (как для аудио)
- Ограничение длительности видео (Canvas-стиль или длина трека)
- Учёт видео в storage quota пользователя

## Метаданные трека

- Изменение `is_public` после загрузки (PATCH)
- Загрузка/замена обложки
- Загрузка/удаление видео
- Текст песни (plain text) + синхронизированные тайм-коды
- **Редактирование title, artist, genre после загрузки**
  - `TrackUpdateRequest` расширен (Optional поля title/artist/genre/description)
  - `TrackRepository.update_track()` + `TrackService.update_track()`
  - PATCH endpoint обновлён: принимает любую комбинацию полей
- Поле `description` в модели Track (TEXT, nullable)
  - Alembic миграция `651109411149`
- **Автоопределение текста песен (lyrics auto-detection)**
  - Весь пайплайн в PrivateCore (чёрная коробка)
  - Backend: тонкий адаптер (S3 download, вызов PrivateCore, сохранение в БД)
  - Выбор режима: "Определить текст" (без таймкодов) / "Определить текст + таймкоды"
  - Кеш таймкодов: synced_lines хранятся в БД, переключение без пересчёта
  - Редактирование автосгенерированного текста, source manual/auto
  - Поддержка внешних треков без аудио (только текст)
  - Миграция 0030: колонка source в track_lyrics
  - Taskiq-задача generate_lyrics_task
  - API: POST /lyrics/auto, GET /lyrics/auto/status
  - Frontend: кнопки автогенерации, toggle таймкодов, i18n
  - Re-define fix: админ-кнопки с `bypass_cache=true` + расширенные debug-логи в карточке (шестерёнка)
  - Search fallback fix: при miss по `(artist,title)` делаем retry по `title-only` и сохраняем cache alias
  - Stability fix (2026-04-25): remote catalog-align теперь получает `audio_seconds` от compute-worker для корректной шкалы времени; добавлен защитный rescue от схлопнутой line-sync таймлинии (когда строки прилипают к одному позднему якорю), плюс retry на отправку `result/fail` из worker.
- **Auto-lyrics: вынос тяжёлой обработки на внешний GPU-сервис (далёкое будущее)**
  - Отдельный сервер/сервис с GPU для обработки аудио
  - Backend отправляет аудиофайл во внутренний API PrivateCore,
  а PrivateCore уже сам решает, обрабатывать локально или вызывать внешний GPU-сервис
  - Интеграция через существующий `lyrics_provider` в PrivateCore (внешние детали — внутри чёрного ящика)
- [ ] **Karaoke после catalog + remote ASR align (пока не делаем):**
  UI показывает режим «Караоке» только при `word_times` на строках
  **и** `sync_quality === "word"` (`LyricsPanel.tsx`, `FullscreenLyrics.tsx`).
  Ветка `POST .../audio-compute/.../result` с
  `align_text_to_precomputed_asr_timed_words` сейчас пишет в БД
  **только** line-level строки + `sync_quality=line` — словесные
  таймкоды с воркера в сохранённый JSON не переносятся. На будущее:
  после align приклеить/распределить `word_times` к выровненным
  строкам каталога (из `asr_timed_words` или исходных
  `synced_lines` воркера) и при успехе выставлять `word`, чтобы
  караоке снова работал при эталонном тексте.
- Теги (`tags`, JSONB или отдельная таблица)
- BPM auto-detection (background task, `librosa` / `essentia`)
  - Извлечение фич/пороги confidence и decision rules в PrivateCore, Taskiq orchestration и запись результата — в Backend
- Waveform generation (pre-render формы волны для UI)

## Чат и комментарии

- Чат: DM, группы, WebSocket real-time
- Реакции, вложения, голосовые сообщения, шифрование
- WebSocket: Redis pub/sub, presence, typing indicators
- Комментарии к трекам: CRUD, голосование, пин, скрытие
- [~] Доработки чата (обсудить отдельно)

## Карточка артиста (multi-source)

- Policy-exception для явного source attribution
(`source_name` + `source_page_url`) зафиксирован в
`docs/ai-boundary-policy.md` (Backend + PrivateCore)
- PrivateCore: расширен контракт `ArtistInfo` полями
`source_profiles`, `primary_source_id`, `discography`
- Backend: добавлены `artists.source_profiles` (JSON) и
`artists.primary_source_id` (миграция `0039`)
- Backend API: `ArtistDetailResponse` и `/api/v1/artists/{id}`
возвращают `source_profiles` и `primary_source_id`
- Frontend ArtistView: горизонтальный переключатель источников
под аватаром + рендер bio/meta/discography по выбранному источнику
- Frontend ArtistView: полноэкранный просмотр аватарки с
закрытием по overlay / кнопке / `Esc`
- Frontend ArtistView: отдельная строка
`Источник: <source_name>` с кликабельной ссылкой на страницу
источника
- Регрессионные тесты обновлены:
  - PrivateCore `test_artist_info_provider.py`
  - Backend `test_artist_enrichment_service.py`,
  `test_artist_enrich.py`, `test_artist.py`

## Предзагрузка треков

- Предзагрузка следующей пачки в боте (DotSoundBot)
- `GET /tracks/{id}/adjacent` (sequential/shuffle/repeat_one)
- hls.js с ABR (`startLevel: -1`, `enableWorker: true`)
- **Prefetch в Mini App / браузере (метаданные)**
  - `GET /tracks/{id}/queue?count=3` -- новый endpoint
  - `TrackRepository.get_next_tracks()` возвращает N следующих треков
  - Кеш в `PlayerContext` через `useRef` (`prefetchCacheRef`)
  - `playNext` использует кеш, fallback на `getAdjacentTracks`
- **Предзагрузка аудио следующего трека (gapless)**
  - При проигрывании текущего трека — начинать буферизацию аудио следующего трека в фоне
  - Скрытый `<audio>` элемент (`preloadAudioRef`) с `preload="auto"` загружает URL следующего трека
  - Для HLS: создать второй `Hls` instance, привязать к preload-элементу, дождаться `MANIFEST_PARSED`
  - При `playNext` — swap: preload-элемент становится основным, мгновенный старт без буферизации
  - Запуск предзагрузки по порогу (например, текущий трек проигран на 75% или осталось < 30 сек)
  - Отмена предзагрузки при ручном переключении на другой трек
  - Ограничение: предзагружать только 1 следующий трек (экономия трафика)

## Идентификация загрузчика

- `uploaded_by_id` на Track (FK -> User с telegram_id)
- `created_at` / `updated_at` timestamps
- `RequestLoggingMiddleware` логирует `client_ip` в structlog
- **Расширенные метаданные загрузки (admin-only)**
  - Модель `TrackUploadMeta` (миграция `0022`): `upload_ip`, `upload_user_agent`, `upload_telegram_data` (JSON)
  - Заполнение при upload из `request.client.host` + headers
  - Admin endpoint `GET /admin/tracks/{id}/upload-meta`
  - PrivateCore: `UPLOAD_META_RETENTION_DAYS = 90`
- Taskiq job для автоудаления meta старше retention (GDPR)

## Удаление аккаунта

- **Soft delete с grace period (30 дней)**
  - `DELETE /api/v1/users/me` (body: `{"confirmation": "DELETE"}`)
  - `POST /api/v1/users/me/restore` -- восстановление в grace period
  - `deleted_at` на User (миграция `0021`)
  - PrivateCore: `account_deletion_policy.py` (GRACE_PERIOD_DAYS, is_within_grace_period, is_valid_confirmation)
  - Auth flow: soft-deleted пользователи в grace period проходят auth
- Taskiq job для hard delete после 30 дней
- **Политика удаления данных**
  - Профиль, аватар, настройки EQ -- удалить
  - Лайки, дизлайки, подписки -- удалить
  - Сообщения в чатах -- анонимизировать ("Deleted User")
  - Комментарии -- анонимизировать
  - Плейлисты -- удалить
  - Треки -- выбор пользователя: удалить или оставить анонимно
  - S3 объекты -- удалить при удалении трека
- **Подтверждение удаления**
  - Повторная авторизация
  - Текстовое подтверждение ("DELETE")
  - Email/Telegram уведомление
  - Политику re-auth/cooldown/max-attempts для удаления хранить в PrivateCore

## Frontend / Mini App

- [x] Главная: CTA «Слушать/Play» — старт с первого трека плейлиста дня
  (дальше — существующий radio-prefetch в `PlayerContext`); карточка
  «плейлист недели» и экран `/weekly-mix` (API `weekly-playlist`).
- Восстановление позиции воспроизведения при перезапуске
- Монохром-фильтр в настройках
- Админ-панель: управление пользователями
  - Если добавятся баны/risk flags/anti-abuse actions, decision rules и пороги должны идти из PrivateCore
- Админ-панель: модерация контента
  - Пороги auto-hide/escalation и moderation policy держать в PrivateCore, панель — UI + вызовы Backend API
- Админ-панель: управление бэкапами (см. выше)

## Frontend оптимизация

- [x] **Waveform (карточка трека): снижение нагрузки на iGPU** — rAF и
  отрисовка спектра только при `isPlaying` (не 60 fps в паузе),
  ~30 fps для декоративного спектра
- [x] **PlayerContext: CPU** — throttling обновлений `currentTime` в React
  (~10/s), flush при play/pause/seek/skip; вьюхи и экраны без таймера
  переведены с `usePlayer()` на `usePlayerActions` / `usePlayerMeta`, чтобы
  не перерисовываться на каждый тик
- [x] **SearchView: прогрессивная выдача** — `getTracks` / `searchSuggest`
  не ждут YouTube, Bandcamp, SoundCloud; внешние секции обновляются
  по мере ответа и могут отображаться до готовности блока «На платформе»
- **PlayerContext split (производительность)**
  - 3 контекста: `PlayerStateCtx` (currentTime, duration, isPlaying),
  `PlayerActionsCtx` (стабильные callbacks через useCallback),
  `PlayerMetaCtx` (track, volume, EQ, модалки)
  - 3 хука: `usePlayerState()`, `usePlayerActions()`, `usePlayerMeta()`
  - `usePlayer()` -- compat shim для плавной миграции
- **LikesContext оптимизация**
  - `useMemo` на value, `useCallback` на все функции
- **React Router (deep links, PWA)**
  - `react-router-dom` v7 (React Router)
  - Маршруты: `/`, `/search`, `/upload`, `/liked`, `/playlists`,
  `/chats`, `/chats/:id`, `/profile`, `/track/:trackId`
  - `BottomNav` через `useNavigate` + `useLocation`
  - `BrowserRouter basename="/mini_app"`
  - Browser back/forward, shareable URLs, deep links
- **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView, LikedView, PlaylistsView, ChatsView, ProfileView
  - `hls.js` в отдельный chunk (`manualChunks`)
  - `<Suspense>` обёртка для route-level lazy loading
- **TanStack Query (API кеширование)**
  - Автоматический кеш, дедупликация, stale-while-revalidate
  - Постепенное внедрение (endpoint за endpoint)
- Типизация: убрать 5x `Promise<any>` в `api.ts`
  - `ImportJobResponse` + `ImportAudioInfo` в `types/api.ts`
  - `genre` + `description` добавлены в `Track` interface
- CSS: рассмотреть разделение `global.css` (~2700 строк)

## Backend API

- [x] YouTube import/playback: fallback на auto-выбор формата в
  `yt-dlp` при `Requested format is not available` (без 422/503 из-за
  жёсткого format-string)
- [x] YouTube import/playback: fallback по client-профилям `yt-dlp`
  при anti-bot (`Sign in to confirm you’re not a bot`) + возврат 503
  вместо 422 для временной блокировки
- [x] **Elasticsearch (поиск + suggest)**: индексы треков/артистов,
  Taskiq reindex/backfill, `GET /api/v1/search/suggest`, поиск треков
  с `q` через ES + PG fallback, bool/should (strict + fuzzy) для треков/артистов
  и саджеста, counter `elasticsearch_query_total` (op/outcome) в `observability`
- [x] `artist_link_backfill_task` / `track_artists`: дедуп по
  `canonical` (PrivateCore + `resolve_and_link`), `ON CONFLICT DO NOTHING`
  в `link_track`, `begin_nested` + `error`/`error_type` в backfill
- [x] `LOG_THIRD_PARTY_LEVEL` / `apply_third_party_log_levels` — уровень
  ``urllib3``/httpx/ES/SQL-эха отдельно от ``LOG_LEVEL``; Taskiq воркеры
  тоже при старте
- playable_only фильтр в track listing endpoints
- internal-token endpoint с полной защитой
- WebSocket: событие player.state для синхронизации
- Пагинация liked tracks (backend + frontend)
  - Backend: `page`/`has_more` в `UserLikesResponse`
  - Frontend: `LikedView` с "Показать ещё" кнопкой

## Юридический аудит: анализ конкурентов (UGC + ст. 1253.1)

> **Цель**: изучить каждый сервис из списка на 2 вещи:
>
> 1. Наличие web-плеера / API для стриминга — возможна ли ретрансляция
>   аудио на DotSound (аналогично SoundCloud: звук передаётся
>    пользователю, плеер наш, мы оболочка).
> 2. Политика, соглашения, правовая реализация — что можно
>   адаптировать для DotSound (тексты оферт, дисклеймеры,
>    процедуры takedown, формы загрузки с подтверждением прав).

### Категория 1: Прямые аналоги (UGC + информационный посредник)

- **Musify.club**
  - Web-плеер: есть ли публичный стрим/API, можно ли встроить
  - Юридика: пользовательское соглашение (ст. 1253.1), страница
  `/contacts/legal` (перечень лицензий с ООО «АдвМьюзик» и др.),
  процедура DMCA/takedown, форма загрузки
  - Выводы: что адаптировать для DotSound
- **4beat.ru**
  - Web-плеер: стрим, embed, API
  - Юридика: пользовательское соглашение, форма загрузки трека
  (какие галочки/подтверждения прав требуют), страница правообладателям
  - Выводы: что адаптировать для DotSound
- **QPlet.ru**
  - Web-плеер: стрим, публичный доступ к аудио
  - Юридика: условия загрузки, онбординг артиста, оферта
  - Выводы: что адаптировать для DotSound
- **Созвук (sozvuk.ru)**
  - Web-плеер: стрим, embed, API для треков
  - Юридика: публичная оферта (ст. 1253.1), как оформлены права
  при загрузке, политика удаления по жалобе
  - Выводы: что адаптировать для DotSound

### Категория 2: Крупные платформы с UGC-компонентом

- **VK Музыка (vk.com/music)**
  - Web-плеер: закрытый API, возможность ретрансляции
  - Юридика: лицензионное соглашение (`vk.com/terms/music`),
  Content ID, как разделяют лицензированный и UGC-контент,
  процедура жалоб
  - Выводы: что адаптировать для DotSound
- **Яндекс.Музыка**
  - Web-плеер: закрытый стрим, ранжирование UGC vs лицензированное
  - Юридика: условия загрузки пользовательской музыки,
  как UGC показывается ниже официального в поиске
  - Выводы: что адаптировать для DotSound
- **ZVUK (zvuk.com)**
  - Web-плеер: стрим, партнёрская модель
  - Юридика: условия для артистов, договоры с дистрибьюторами,
  требования к правам
  - Выводы: что адаптировать для DotSound

### Категория 3: Серая зона

- **Зайцев.НЕТ (zaycev.net)**
  - Web-плеер: стрим, API, текущая модель (100% лицензии с 2019)
  - Юридика: путь от UGC к лицензиям — что заставило перейти,
  пользовательское соглашение (написано юристами), страница
  правообладателям, процедура 5-дневного takedown
  - Выводы: какие тексты/процедуры адаптировать для DotSound
- **TRULA-music (trula-music.ru)**
  - Web-плеер: плеер + виджеты для стримеров
  - Юридика: оферта (ст. 1253.1), узкая ниша — как оформляют права
  - Выводы: что адаптировать для DotSound
- **Muzofond.fm / LightAudio.ru / HitMo (антипримеры)**
  - Web-плеер: открытый стрим, скачивание mp3
  - Юридика: нет явных лицензий, ссылаются на «пользователи
  загрузили», периодические блокировки Роскомнадзора
  - Выводы: какие ошибки НЕ повторять

### Итоговый отчёт (после анализа всех сервисов)

- Сводная таблица: сервис / web-API / возможность ретрансляции /
юридическая модель / риски / что адаптировать
- Список конкретных текстов для адаптации: оферта, дисклеймер,
страница правообладателям, форма загрузки с подтверждением прав
- Рекомендации по изменению архитектуры DotSound на основе анализа

## Юридическая готовность

- Базовый legal package в репозитории
  - `LEGAL.md`
  - `docs/legal/archive/LEGAL_AUDIT_RU.md`
  - `docs/legal/USER_AGREEMENT.md`
  - `docs/legal/PRIVACY_POLICY.md`
  - `docs/legal/COPYRIGHT_POLICY.md`
  - `docs/legal/UPLOAD_RULES.md`
  - `docs/legal/LEGAL_TEXTS.md`
- Синхронизировать complaint/rightsholder flow во frontend и backend
  - `reason_type`, `rightsholder_name`, `proof_url` теперь проходят
  через schema -> route -> service -> repository -> UI
- Обязательный акцепт условий при `UGC` upload
  - Checkbox в `UploadFileTab.tsx`
  - backend validation в `api/v1/tracks/user.py`
  - логирование версии условий в `track_upload_meta`
- Постоянные guardrails для агентов и docs
  - `AGENTS.md`
  - `docs/ai-boundary-policy.md`
  - `.cursor/rules/legal-readiness.mdc`
  - `.claude/hooks` + `.claude/settings.json`:
  блок опасных shell-patterns, блок секретов, SessionStart контекст
  - `.cursor/rules/shell-safety.mdc` + `.cursor/rules/session-start-context.mdc`
  для эквивалентных guardrails в Cursor
- Явно размечен current MVP external playback
  - В `Track` добавлены `access_mode`, `source_platform`,
  `canonical_source_url`
  - `SoundCloud` import помечает трек как
  `third_party_stream`
  - UI показывает внешний источник и режим доступа
- На уровне модели разделены категории треков
  - В `Track` добавлен `catalog_type`
  - Базовое разделение: `ugc`, `licensed`, `external_reference`
  - `SoundCloud` -> `external_reference`, `upload/telegram` -> `ugc`
- Опубликовать legal docs в самом продукте как отдельные доступные
страницы
  - `/legal` стал hub-страницей
  - Добавлены маршруты `/legal/terms`, `/legal/privacy`,
  `/legal/copyright`, `/legal/upload-rules`
  - Upload и complaint flow теперь ссылаются на конкретные legal docs
- Разделить на уровне модели/API `UGC`, `licensed` и
`external-source` треки, не полагаясь только на текстовые
дисклеймеры
- Проверить current MVP с собственным playback поверх
stream URL стороннего сервиса для текущего внешнего источника
(`SoundCloud`) и зафиксировать residual risk
- Разделить обычную пользовательскую жалобу и надлежащее
уведомление правообладателя в отдельные UX и workflow
- Базово разделить обычную жалобу и уведомление правообладателя
в UX
  - `ComplaintModal` поддерживает режимы `user` и `rightsholder`
  - Правообладательский режим требует доп. поля и отдельный текст
- Internal checklist для Terms внешних источников
  - `docs/legal/SOURCE_TERMS_CHECKLIST.md`
  - rule/docs привязаны к проверке external-source integrations
- Сделать тексты внешнего импорта и поиска более честными
  - `SearchView` явно помечает SoundCloud как внешний источник
  - Текст предупреждает, что после добавления трек идёт как внешний
  поток стороннего сервиса

## DevOps / CI

- **Branch coverage 95% (4 репо):** `scripts/check_branch_coverage.py` + `pytest --cov-branch` / `coverage.json` → порог `percent_branches_covered` (см. Makefile / `AGENTS.md`). Выполнено: полный прогон и проверка gate в Backend/PrivateCore/Bot/ComputeWorker.
- GitHub Actions: lint + test на PR (Backend, Bot, PrivateCore)
- Автоматический деплой на VPS
- Расширенный healthcheck (`/api/v1/health/deep` — БД, Redis, S3)
- Health monitoring + alerting (uptime check, внешний)

## Sprint 0..9 редизайна (2026-04, single-pass)

- Bot: like/dislike — добавлен Bearer + правильный internal id
- Frontend: `--progress` пробрасывается в `#pb-seek` (WebKit fix)
- Frontend: SW unregister только в dev-режиме
- Frontend: `env(safe-area-inset-bottom)` в `#nav`, `#player-bar`, `#main`
- PrivateCore: `is_within_grace_period` отсекает будущие `deleted_at`
- PrivateCore: `is_disposable_email` валидирует формат email
- PrivateCore: тесты для `account_deletion_policy` (15 кейсов)
- Backend: inline SQL вынесен из `artists.py`, `admin/audio_compute.py`
- Backend: `dependencies.require_capability` использует репозиторий
- Backend: `transcoding._upload_hls` использует `asyncio.to_thread`
- Backend: `TrustedHostMiddleware` через `settings.allowed_hosts`
- Bot: throttling middleware подключён к callback и inline_query
- Bot: внутренний HTTP-сервер binds `127.0.0.1` (через config)
- Bot: HTML escape во всех форматтерах (`base`, `audio`, `inline`, `stats`)
- Bot: единый `mini_app_url` (убран `backend_base_url` для WebApp)
- Bot: internal API возвращает opaque error codes
- Bot: глобальный `errors` handler с user-friendly fallback
- Bot: prefetched URLs используются в `_edit_audio_batch` (gap-less)
- Bot: Dockerfile multi-stage с PrivateCore из родительской директории
- Frontend: дизайн-токены в `tokens.css` (8pt grid, motion, type scale)
- Frontend: `components.css` с Press, Sheet, Skeleton, EmptyState стилями
- Frontend: `Press`, `Sheet`, `EmptyState`, `SkeletonList`, `OfflineBanner`
- Frontend: расширен Icon-set (more-horizontal, queue, chevron-up/down)
- Frontend: Unicode заменён на `<Icon>` в FullscreenLyrics, PlaylistsView,
ComplaintModal, TrackCard, PlayerBar
- Frontend: `installTelegramThemeBridge`, `installViewportListener`,
`setBackButton`, `haptic`, `hapticNotification`
- Frontend: PlayerBar v2 — overflow menu + breakpoints + skeleton hit-area
- Frontend: TrackCard переключён на `usePlayerMeta` + `usePlayerActions`
- Frontend: CoverImage с `loading="lazy"` + `width/height`
- Frontend: aria-label/aria-pressed/aria-current на ключевых контролах
- Frontend: `useConfirm` переписан с правильным unmount cleanup
- Frontend: index.html splash сокращён с 1800ms до 1200ms safety cap
- PrivateCore: README актуализирован, версия `0.2.0`, policy с
bounded-transport exception
- Backend: `/api/v1/health/deep` (DB / Redis / S3 ping)
- Backend: `X-Request-ID` отдаётся в заголовке ответа
- Docs: `docs/design-system.md`, `docs/redesign-rationale.md`

---

*Последнее обновление: 2026-04-24 (multi-platform streaming: YouTube + Bandcamp).*

## Платформы — будущее

- [ ] **Гибридный плеер**: для платформ с официальными embed-виджетами реализовать
  `access_mode="official_embed"` — хранить embed URL, отрисовывать `<iframe>` вместо
  нативного плеера, отключить EQ. Приоритет: YouTube (требует TOS раздел 5.D).
- [ ] **VK Музыка**: OAuth уже реализован (`linked_accounts`, scope `audio`). Нужно добавить
  `VKStreamService` (получает HLS-URL через `audio.getById` с user OAuth token) и расширить
  `playback.py`. Отложено — российский сервис.
- [ ] **Яндекс Музыка**: нужен новый OAuth-провайдер (`Yandex OAuth`, oauth.yandex.ru) +
  неофициальный API-адаптер. Отложено — российский сервис.
- [ ] **YouTube TOS compliance**: согласно TOS YouTube раздел 5.D прямой API-стриминг запрещён.
  Долгосрочно: мигрировать на `access_mode="official_embed"` (iframe-embed), API-стриминг
  оставить только как dev/fallback.

## Sprint concurrency hardening (2026-04-22)

- Backend: миграция `0045_dedupe_unique_constraints` — partial UNIQUE
  на `tracks.sc_url WHERE sc_url IS NOT NULL` и на
  `(imported_from, external_id) WHERE external_id IS NOT NULL`,
  `Index` объявлены в `app/models/track.py:Track.__table_args__`
  (создаются и для тестовой SQLite-схемы)
- Backend: `scripts/dedupe_tracks.py` — pre-migration helper, dry-run
  по умолчанию, мерджит дубли по `sc_url` и `(imported_from, external_id)`
  с union-find и FK-redirect для likes/dislikes/playlists/track_artists/
  track_lyrics/track_info/track_upload_meta/complaints/listen_events/
  comments/lyrics_jobs/search_events/messages
- Backend: `SoundCloudService.import_or_get_track` переписан на
  `INSERT ... ON CONFLICT (sc_url) WHERE sc_url IS NOT NULL DO NOTHING
  RETURNING` + fallback `SELECT`; `external_import_worker` обёрнут в
  `try/except IntegrityError` на случай rolldown-сценария
- Backend: миграция `0046_add_lyrics_sync_source_name` —
  `track_lyrics.sync_source_name VARCHAR(50) NULL`, проброс через
  `LyricsRepository.create_or_update`, `LyricsResponse` schema,
  `_result_to_payload(getattr(gen_result, "sync_source_name", None))`
- Backend: `app/services/sc_semaphore.py` — Redis-based counting
  semaphore (sorted-set + Lua acquire) вокруг SoundCloud `search`/
  `resolve_url`/`get_stream_info`, env `SOUNDCLOUD_GLOBAL_CONCURRENCY=4`
- Backend: per-track Redis lock в `lyrics_worker.generate_lyrics_task`
  (рефакторинг через outer wrapper + `_generate_lyrics_task_impl`),
  env `LYRICS_PER_TRACK_LOCK_TTL_SECONDS=300`; race-protected
  через `SET NX EX` + Lua-release-on-match
- Backend: `app/services/import_queue_dispatcher.py` — backpressure
  через статус `"queued"`, env `IMPORT_MAX_CONCURRENT_JOBS=10`,
  `IMPORT_PER_USER_MAX_CONCURRENT=2`, dispatcher loop запускается
  в WORKER_STARTUP. `ImportService.start_import` возвращает job
  с `status="queued"` если глобальный или per-user cap занят;
  `get_queue_position` для UI; `cancel_job` и `_get_active_job`
  понимают `"queued"`
- Backend: `app/services/lyrics_global_orchestrator.py` —
  единый pacer через `BLPOP lyrics:queue:default`, фичефлаг
  `LYRICS_GLOBAL_ORCHESTRATOR_ENABLED=true`, заменяет per-job
  пейсинг в `import_lyrics_worker.process_import_lyrics_task`
  (legacy mode сохранён, активируется выключением флага). Global
  circuit-breaker на 5 подряд `captcha|pool_exhaust|exhausted`
  сигналов из proxy_pool
- Backend: API `GET /import/{id}/status` и `/import/active`
  возвращают `queue_position` для queued джобов
- Backend: `main.py` зарегистрировал воркеры
  `app.services.import_queue_dispatcher` и
  `app.services.lyrics_global_orchestrator`
- Frontend: `ImportView.tsx` — новая фаза `"queued"` с
  отображением `queue_position`, polling переключается между
  `queued <-> importing` без пересоздания интервала
- Frontend: `LyricsPanel.tsx` и `FullscreenLyrics.tsx` — admin-only
  debug-блок «Источник текста» / «Синхронизовал» в самом конце
  отображённого текста, гейтится через `getIsAdmin()`; CSS
  `.lyrics-debug-attribution` (минимализм, монохром, monospace)
- Docs: `docs/private-core-dependency-policy.md` пополнен таблицей
  опциональных полей `GenerateResult` (включая новый
  `sync_source_name` — PrivateCore-side требуется добавить поле,
  Backend уже forward-compatible через `getattr`)
- Tests: `test_soundcloud_service::test_import_or_get_track_dedup_via_unique_index`,
  `test_lyrics_worker::test_sync_source_name_propagates_to_repo`,
  `test_lyrics_global_orchestrator.py` (новый файл, 7 тестов на
  serialize/deserialize/process_one), `test_import_service` (3 новых
  теста на backpressure + queue_position + cancel queued),
  `test_import_lyrics_worker` autouse-фикстура форсит legacy режим

## Sprint multi-importer library (2026-04-22)

- Backend: миграция `0047_add_user_track_library` — many-to-many
  таблица `user_track_library (user_id, track_id, source,
  imported_at)` с composite PK + индекс `(user_id, imported_at)`.
  Backfill из `tracks.uploaded_by_id` чтобы существующие треки
  попали в библиотеку владельца
- Backend: `app/models/user_track_library.py` (модель) +
  `app/repositories/user_track_library.py` (`add` идемпотентен
  через `INSERT ... ON CONFLICT DO NOTHING`, `list_by_user`,
  `count_by_user`, `has`, `remove`)
- Backend: auto-link во всех flow создания трека —
  `external_import_worker.py` (после `import_or_get_track`,
  включая dedup-resolved случай), `import_worker.py` (telegram),
  `upload_service.py` (UGC). Идемпотентно — повторный импорт
  одной песни одним юзером не дублирует
- Backend: `GET /api/v1/users/me/library` — paginated, ORDER BY
  `imported_at DESC`, `playable_only` filter; `TrackService.list_library`,
  `UserTrackLibraryRepository.list_by_user` с JOIN
- Backend: `LyricsService._get_editable_track` — для
  `catalog_type='external_reference'` редактирование лирики только
  админом, для UGC оригинальный uploader (как раньше). Все методы
  `create_or_update`/`update_sync`/`delete_lyrics`/`redefine`/
  `trigger_auto_generation`/`cancel_auto_generation` переведены
  на новую проверку
- Backend: defensive `LyricsRepository.get_by_track_id` skip в
  `lyrics_global_orchestrator._process_one` — закрывает race
  window между `_enqueue_to_global_queue` и моментом обработки
  (другой воркер мог уже сохранить лирику)
- Frontend: `api.getMyLibrary(page, size, playableOnly)` метод;
  `ProfileView` переключён с `getMyTracks` на `getMyLibrary`,
  пользователь видит и свои аплоады, и импортированные треки
- Frontend: `LyricsPanel` принимает `catalogType` prop, кнопки
  редактирования гейтятся через `canEdit = isExternalRef ?
  isAdmin : isOwner`. Все 4 точки ownership-gating обновлены.
  `TrackCardSheet` пробрасывает `catalog_type`, edit-pane lyrics-toggle
  кнопка скрыта для non-admin на external_reference
- Frontend: `ImportView` фаза `done` показывает «Треки добавлены
  в вашу библиотеку (профиль)»
- Tests: `test_user_track_library.py` (7 кейсов: idempotency,
  shared-by-two-users, ordering, remove, count, has),
  `test_external_import_worker::test_two_users_share_track_with_two_library_links`,
  `test_lyrics_service` (3 новых: external blocks owner, allows admin,
  ugc owner ok), `test_lyrics_global_orchestrator::test_process_one_skips_when_lyrics_already_in_db`

## Sprint admin / auth (2026-04-19)

- Frontend: синхронный `api.restoreSession()` в `main.tsx` ДО рендера — убирает раннюю гонку токена с AdminProvider/PlayerProvider
- Frontend: `AdminContext.tsx` гейтит `getAdminManifest()` на наличие токена и подписан на `app-auth-ready` + `i18n.languageChanged`; убран orphan-импорт `adminBundleUrl`
- Frontend: `App.init()` пропускает `api.authTelegram('')` при пустом initData (убирает 422 + 500ms ретрай в ngrok-режиме)
- Frontend: `connectWS(...)` вызывается сразу в `verifyTelegramCode` / `verifyMagicLink` / `verify2FA`, плюс диспатч `app-auth-ready`
- Frontend: `restoreSession()` восстанавливает `auth-user-id` из JWT `sub`, если он потерян — убирает «при обновлении просит код»
- Frontend: Suspense fallback с timeout-ом и retry в `App.tsx` (`RouteFallback`) — убирает «чёрный экран» при зависших lazy-чанках
- Frontend: i18n RU/EN для всей админки (`admin.`* namespace в локалях, `useTranslation` в `AdminApp`, `AdminShell`, всех auth-формах и routes)
- Frontend: `AuthGate` запускает `ensureCsrf` и `bootstrapMetadata` параллельно через `Promise.allSettled` и пытается `adminApi.refresh()` на старте — admin-сессия переживает reload без TOTP
- Frontend: `useAdminAuth.capabilities` наполняется из манифеста после успешного refresh — `useCapability` теперь работает
- Frontend: proactive refresh за 30 сек до expiry в `adminFetch`; при фейле refresh статус `'needs_login'` вместо `'unauth'`
- Frontend: `AdminShell` — часы вынесены в изолированный `<Clock />`, остальная панель не перерисовывается каждую секунду
- Frontend: refetchInterval поднят до 15-30 сек и `refetchIntervalInBackground: false` во всех админ-routes (Dashboard, Logs, Tasks, Metrics, Containers, Security, Settings, AudioCompute)
- Frontend: удалён orphan-файл `frontend/src/admin/AdminDashboardView.tsx`
- Frontend: `?nosw=1` в URL разрегистрирует service worker (отладка на ngrok)
- Frontend: убран дублирующий `<Route path="/admin">` без `*` в `App.tsx` — nested `<Routes>` в `AdminApp` теперь корректно рендерит `DashboardRoute`
- Frontend: `adminApi.refresh()` и `adminApi.logout()` больше не шлют `body: {}` — backend теперь читает refresh token из httpOnly-cookie без 422 от валидации `AdminRefreshRequest`

## Sprint bugfix (2026-04-20)

- **(0)** Policy amendment: расширить "Source Attribution Exception" на lyrics / track-info провайдеров (`CLAUDE.md` + `docs/ai-boundary-policy.md`)
- **(1)** Track info: перенос из внешней кнопки внутрь `TrackCardSheet` (после блока «похожие треки»), DEBUG-refresh (admin), автозагрузка и polling
- **(2)** Track info worker: `/api/v1/tracks/{id}/info` зависает в `fetching` — stale-retry в сервисе, `asyncio.wait_for` timeout 90s в воркере, `fetched_at` отражает последнее состояние
- **(3)** `TrackCardSheet`: белая заливка прогресс-бара — CSS gradient с `--progress` + inline style на seek-input
- **(4)** `SettingsSheet`: кнопка «Назад» с label + Telegram BackButton + Esc
- **(5)** `TrackCardSheet`: крестик 44×44, safe-area-inset-top/right, не выходит за рамки
- **(6)** `TrackCardSheet`: «Перейти к автору» использует `track.artist` через `onOpenArtist`; ряд загрузчика переименован
- **(7)** Admin: `/logs/query` и `/metrics/range` возвращают `source_status` + `/system/observability` endpoint, banner в `LogsRoute` / `MetricsRoute`
- **(8)** Admin lyrics-jobs: индивидуальный cancel (inline-кнопка) + bulk `POST /tasks/lyrics-jobs/cancel-queued`; `queued` сразу переводится в `cancelled` в БД
- **(9)** Admin Artists: `DELETE /artists/{id}`, клик по имени → `/mini_app/artist/:id` (новая вкладка), fix даты через fallback на `created_at`, `updated_at` добавлен в `ArtistResponse`
- **(10)** Admin Tracks: existing `DELETE` + visibility-toggle + inline `<audio>` + открытие `/mini_app/track/:id`
- **(11)** Admin Users: ban/unban + `POST /users-ext/{id}/force-logout` (revoke admin sessions + Redis marker) + `POST /users-ext/{id}/message` (DM через `ChatService`/`MessageService`)
- **(12)** Lyrics: cache-hit с text-only при `with_sync=true` пре-сохраняет текст в БД и продолжает в audio-based sync flow
- **(13)** WS: `_is_ws_open()` guard + `try/except (WebSocketDisconnect, RuntimeError)` → ранний выход из `_broadcast_loop`
- **(14)** Lyrics: `LyricsResponse.source_name` (optional) для UI-attribution + `lyrics_provider_name` / `track_info_provider_name` env-flag selectors; алгоритмика остаётся в PrivateCore