# DotSound �?? TODO Tracker

> Э�?о�? �?айл подде�?живае�?ся ав�?ома�?и�?ески �?�?-аген�?ом.
> Аген�? обязан: (1) п�?о�?и�?а�?�? э�?о�? �?айл в на�?але сессии,
> (2) обнови�?�? с�?а�?�?с�? после в�?полнения зада�?,
> (3) добави�?�? нов�?е зада�?и если они возникли.

## С�?а�?�?с�?

- `[ ]` �?? не на�?а�?о
- `[~]` �?? в п�?о�?ессе
- `[x]` �?? заве�?�?ено
- `[-]` �?? о�?менено / неак�?�?ал�?но

---

## Smart-buffering / pre-fetch (2026-05-06)

- [x] **Smart predictive audio buffering (Mini App)** — единый
  PrefetchManager на фронте, IndexedDB warm-index + Service-Worker
  Cache API (через `vite-plugin-pwa` runtimeCaching) для HLS-сегментов
  и progressive-audio.
  - PrivateCore: `services/prefetch_policy.py` — константы и decision
    функции (`decide_lookahead`, `decide_max_storage_bytes`,
    `decide_warm_segments_per_track`, `should_prefetch_in_context`,
    `build_policy_snapshot`) + `NetworkProfile`/`PrefetchPolicySnapshot`
    + 24 unit-теста.
  - Backend: `GET /api/v1/prefetch/policy` (stateless) принимает
    client-hints (`effective_type`, `save_data`, `downlink`,
    `quota_bytes`) и отдаёт snapshot из PrivateCore. Pydantic-схема
    `app/schemas/prefetch.py`, тесты `tests/app/api/v1/test_prefetch.py`.
  - Frontend: `lib/prefetch/PrefetchManager.ts` (priority queue,
    semaphore, network listener, IndexedDB LRU), `store/PrefetchContext.tsx`
    + `usePrefetch`/`usePrefetchTracks`, тоггл «Умная буферизация» в
    `SettingsSheet`. Интеграция в `PlayerContext` (доп. слой к
    in-memory gapless handoff).
  - Триггеры prefetch: `HomeView`, `ArtistView`, `GenreMixView`,
    `WeeklyTopView`, `WeeklyMixView`, `DailyMixView`, `UserChoiceView`,
    `LikedView`, `SearchView` (top-3), `TrackCardSheet` (similar),
    `ChatBubble` (shared track), deep-link `/track/:id`,
    `continue_on_app_start` (последний трек history).
  - SW caching: HLS manifests SWR, HLS-segments CacheFirst (240
    entries, range-requests), progressive audio CacheFirst
    (`purgeOnQuotaError`).
  - Third-party stream треки (`access_mode == 'third_party_stream'`,
    SoundCloud/YouTube/Bandcamp) не кешируются локально — только
    metadata + URL warm-up через существующий `audio_cache_prefetch`.

## Mini App / .sound UI (2026-05-04)

- [x] **Admin + lyrics pipeline: жан�? и нас�?�?оение по �?екс�?�?** �??
  эв�?ис�?ика в PrivateCore (`text_genre_mood_infer`), ав�?оп�?именение
  после `LyricsRepository.create_or_update`, batch prompt/import в
  админ-�?�?ека�? и `LYRICS_DERIVED_GENRE_MOOD_ENABLED` в `.env.example`.
- [x] **View Transitions + React** �?? `flushSync` в колбэке
  `startViewTransition` в `App.tsx` (ина�?е снимок «нового» кад�?а до комми�?а
  React �?? п�?с�?ой/�?�?�?н�?й эк�?ан п�?и смене вкладок/ма�?�?�?�?�?ов).
- [x] **�?лобал�?н�?й UI redesign `.sound`** �?? обновлен�? splash/loading,
  иконки PWA, дома�?ний эк�?ан, поиск, �?а�?�?, п�?о�?ил�?, admin shell и
  Telegram bot copy/keyboards без изменения backend API, PrivateCore и
  ComputeWorker.
- [x] **Upload UX redesign + genre search** �?? UploadView/Upload tabs пол�?�?или
  iOS-like polish, добавлено �?мное combobox с ES-backed fuzzy hints и
  create-new-genre flow, пл�?с haptic feedback и акк�?�?а�?н�?е мик�?о-анима�?ии.
- [x] **Upload: profile-owned artist flow** �?? `one account -> one artist`
  ownership (backend by user id), unique-name enforcement with migration
  auto-dedupe, auto-rename owned artist on `display_name` update, and
  UploadFileTab mode switch (`I am this artist` vs manual artist).
- [ ] **Home recommendations: richer highlight endpoint** �?? добави�?�?
  о�?дел�?н�?е данн�?е для к�?�?пной ка�?�?о�?ки главного эк�?ана: editorial label,
  reason/highlight metadata, с�?абил�?н�?й hero image и компак�?н�?е carousel
  controls. Реализова�?�? о�?дел�?н�?м backend/frontend п�?о�?одом после review
  г�?ани�?�? Backend/PrivateCore; �?ек�?�?ий UI испол�?з�?е�? с�?�?ес�?в�?�?�?ие
  `continue` / `personalized` / `user_choice` / fallback tracks.

## Админка / ал�?бом�? (2026-05-04)

- [x] **Admin: �?едак�?и�?ование ал�?бомов в UI** �?? колонка `tracks.album_position`
  (миг�?а�?ия `0071`), по�?ядок �?�?еков в п�?бли�?ном `GET /albums/{id}`, API
  `/api/v1/admin/albums` (список, де�?ал�?, PATCH, обложка, add/remove/reorder
  �?�?еков), ма�?�?�?�?�?�? `/admin/albums` и `/admin/albums/:albumId` (capability
  `tracks.manage`).
- [x] **Admin: плейлис�?�?** �?? API `/api/v1/admin/playlists`, UI `/admin/playlists`
  и `/admin/playlists/:playlistId` (ме�?аданн�?е, сос�?ав, по�?ядок; �?пло�?нение
  `playlist_tracks.position` после �?даления).
- [x] **Admin: artist catalog editor UX (2026-05-05)** �?? `ArtistCatalogEditor`
  release metadata + cover upload, per-track title/artist/description/cover,
  paged «all tracks» list; API `POST /api/v1/admin/tracks/{id}/cover`,
  `POST .../catalog/releases/{id}/cover`.

## �?одписки на а�?�?ис�?ов и с�?а�?ис�?ика (2026-04-30)

- [x] **artist_follows** �?? миг�?а�?ия `0068`, модел�?, �?епози�?о�?ий, се�?вис, API:
  `POST/GET /artists/{id}/follow`, `GET /artists/{id}/follow/status`.
  Ав�?о-подписка п�?и онбо�?динге (`save_preferences`).
  `follower_count` + `monthly_listeners` в `ArtistDetailResponse`.
- [x] **Рекоменда�?ии по подпискам** �?? `RecommendationService._build_user_prefs`
  об�?единяе�? `preferred_artist_ids` (онбо�?динг) и `followed_artist_ids` (follows)
  �?е�?ез `dict.fromkeys` (по�?ядок + дед�?плика�?ия).
- [x] **�?о�?ожие а�?�?ис�?�? �?е�?ез SC-с�?ан�?ии (2026-05-01)** �??
  `ArtistCatalogRepository.get_similar_artist_ids_from_stations` извлекае�?
  artist_ids из �?�?еков «�?о�?ожее»-с�?ан�?ий л�?бим�?�? а�?�?ис�?ов; пе�?еда�?�?ся в
  `UserPrefs.similar_artist_ids` (PrivateCore); scoring: 0.5�? vs п�?ям�?�? �?аво�?и�?ов.
  `sync_artist_similar_station_task` + on-follow/onboarding �?�?игге�? в
  `ArtistFollowService._enqueue_station_sync_if_stale`
  (по�?ог `artist_station_stale_threshold_days=7`).
- [x] **Ав�?о-о�?е�?ед�? full catalog sync на follow/onboarding (2026-05-04)** �??
  `ArtistFollowService` �?епе�?�? с�?ави�? `sync_artist_catalog_task` для stale-а�?�?ис�?ов
  (по�?ог `artist_catalog_full_sync_stale_threshold_days=30`) и дед�?пи�? enqueue
  �?е�?ез Redis lock (`artist_catalog_enqueue_lock_ttl_seconds`), �?�?об�? не спами�?�?
  Taskiq п�?и массов�?�? подписка�?.
- [x] **Ак�?ивн�?е сл�?�?а�?ели в меся�?** �?? `artist_monthly_stats` �?абли�?а,
  `ArtistStatsRepository.count_active_listeners` (live из `listen_events`),
  `GET /artists/{id}/stats/listeners` (�?ек�?�?ий меся�? + ис�?о�?ия).
- [x] **Снап�?о�? за п�?о�?л�?й меся�?** �?? Taskiq зада�?а
  `snapshot_monthly_artist_stats_task` (зап�?скае�?ся в�?�?�?н�?�? или
  �?е�?ез вне�?ний cron `0 2 1 * *`). `ArtistStatsService.snapshot_all_artists`.
- [x] **Cron-�?асписание снап�?о�?а** �?? миг�?а�?ия `0069` seed'и�? запис�?
  в `scheduled_jobs` с cron `0 2 1 * *` (TaskiqScheduler / scheduler_service).
- [x] **Рас�?и�?и�?�? `artist_monthly_stats`** �?? миг�?а�?ия `0070`,
  колонки `total_plays`, `total_likes`, `total_followers`;
  `ArtistStatsRepository` + `ArtistStatsService` + с�?ема + frontend types.
  Chart в ArtistView показ�?вае�? данн�?е в tooltip.
- [x] **Frontend: ка�?�?о�?ка а�?�?ис�?а** �?? `follower_count`, `monthly_listeners`
  и кнопка «�?одписа�?�?ся» �?же �?еализован�? в ArtistView (2026-04-30).
- `[ ]` **Frontend: о�?дел�?ная с�?�?ани�?а с�?а�?ис�?ики** �?? `/artist/:id/stats`
  с полно�?енн�?ми recharts-г�?а�?иками (total_plays, total_likes, total_followers
  по меся�?ам). �?азов�?й bar-chart unique_listeners �?же ес�?�? в ArtistView.
- [x] **�?о�?: плее�? �?? ис�?о�?ник «�?одписки»** �?? ис�?о�?ник `follows` добавлен
  в inline-плее�?; `GET /users/me/followed-artists/tracks` (backend),
  `get_followed_artists_tracks` (bot client), кнопка «�??? �?одписки» в мен�?.

## Соо�?ве�?с�?вие 152-Ф�? / �?�?н (backlog, п�?од�?к�? + инжене�?ия)

- �?е�?ед п�?бли�?н�?м зап�?ском: **согласова�?�? с �?�?ис�?ом/�?�?�?** �?ак�?и�?еск�?�?
об�?або�?к�? �?�?н с �?�?ебованиями 152-Ф�? (и смежное): основания, п�?и
необ�?одимос�?и �?ведоми�?ел�?н�?й/�?егис�?�?а�?ионн�?й кон�?�?�?, с�?бп�?о�?ессо�?�?
(email, observability, ASR-облака, бэкап�?), �?�?ансг�?ан, с�?оки �?�?анения,
зап�?ос�? с�?б�?ек�?ов, �?еаги�?ование на ин�?иден�?�?. �?по�?а на `LEGAL.md`,
`docs/legal/PRIVACY_POLICY.md` (сей�?ас draft).
- **Ско�?�?ек�?и�?ова�?�? �?�?нк�?ионал** по и�?огам: �?е�?ен�?н/�?даление,
минимиза�?ия полей, kill-switch вне�?ни�? API, согласованнос�?�? логов и
бэкапов с поли�?икой. Не полага�?�?ся на вн�?�?�?енние id вмес�?о
`telegram_id` как на «анонимиза�?и�?», �?с�?�?аня�?�?�?�? опе�?а�?о�?ские
обязаннос�?и.
- См. �?акже: `docs/project_context.md` (compliance), `AGENTS.md` (Legal
readiness).

## �?�?и�?и�?н�?е / �?н�?�?ас�?�?�?к�?�?�?а

- Сис�?ема бэкапов: PostgreSQL + Redis + configs (локал�?но)
- Сис�?ема логи�?ования: JSON structlog + Docker log rotation
(�?онкая нас�?�?ойка: `REDACT_LOGS`, `REDACT_LOG_IDENTIFIERS`, `LOG_THIRD_PARTY_LEVEL`)
- Outbound Tor pool: по �?мол�?ани�? в�?кл., `TOR_POOL_ENABLED=true` �?? opt-in
- Taskiq worker: graceful shutdown (`WORKER_SHUTDOWN`: cancel
`import_queue_dispatcher` / `lyrics_global_orchestrator` background tasks,
`close_es` в во�?ке�?е) �?? 2026-04
- Docker Compose `worker` service: taskiq modules aligned with
root `main.py` (imports, lyrics queue, snippets) �?? 2026-04
- SoundCloud `get_stream_info`: progressive manifest 404 �?? try HLS
  transcoding before 502; other upstream HTTP errors �?? 502 �?? 2026-04-29
- Audio-compute worker download: OTT with `proxy=1` so Backend
proxies SoundCloud progressive streams (worker no longer GETs
time-bound CDN URL directly; avoids 403) �?? 2026-04
- LyricsJob pull claim: admin profile `remote_whisper` now maps to
  the same queued rows as `gpu_full` (TIER_PROFILE_MAP); tier
  availability heartbeat counts both �?? 2026-04-29
- Mini App плее�?: после сбоя Hls.js fallback `GET /audio` о�?давал
  302 на M3U8, Chrome в `<audio>` M3U8 не декоди�?�?е�? �?? добавлен
  `?force_progressive=true` (п�?окси MP3 с S3) и �?елпе�?
  `trackProgressiveAudioUrl` в плее�?е / о�?�?лайн-кэ�?е / админ-п�?ев�?�?
  �?? 2026-04-27
- �?лее�?: после о�?ибки `getStream` ка�?�?о�?ка в�?з�?вала �?ол�?ко
  `togglePlay` по п�?с�?ом�? audio �?? пов�?о�?ное нажа�?ие Play
  пе�?езап�?скае�? `playTrack`; �?а�?ал�?н�?й HLS без fallback �?? reject;
  dev/admin: override URL по�?ока в ка�?�?о�?ке (sessionStorage)
  �?? 2026-04-29
- Lyrics cascade: preserve **root** worker failure in
`cascade exhausted` message (not only last tier gate, e.g.
`speechkit_disabled`); `lyrics_jobs.request_with_sync` /
`request_bypass_cache` for fallback dispatch; log
`audio_compute_worker_fail` �?? 2026-04
- [x] **Taskiq/cron: weekly batch stale station sweep (2026-05-02)** �??
`ArtistCatalogRepository.find_stale_station_artist_ids(threshold_days)`;
`sync_stale_stations_batch_task` в `artist_catalog_sync_worker`
(enqueue per-artist `sync_artist_similar_station_task`);
миг�?а�?ия `0069` seed'и�? `scheduled_jobs` с cron `0 3 * * 1` (�?н 03:00 UTC).
- **�?олное копи�?ование а�?дио�?айлов (MinIO) на �?дал�?нн�?й backup-VPS**
  - �?одкл�?�?ение к о�?дел�?ном�? се�?ве�?�? по SSH
  - `mc mirror` MinIO -> remote, инк�?емен�?ал�?но
  - Ши�?�?ование �?�?а�?ика, кл�?�?евая а�?�?ен�?и�?ика�?ия
  - Нас�?�?ойка �?е�?ез `.env` (`BACKUP_REMOTE_HOST`)
  - UI в админ-панели: зап�?ск/с�?а�?�?с/�?асписание бэкапа
- Админ-панел�? (frontend): �?аздел �?п�?авления бэкапами
  - �?�?осмо�?�? списка бэкапов, �?азме�?�?, да�?�?
  - Р�?�?ной зап�?ск полного бэкапа
  - Нас�?�?ойка �?асписания
  - С�?а�?�?с последнего бэкапа (OK / FAIL)
  - �?нопка восс�?ановления (с под�?ве�?ждением)

## Админ-панел�? (в�?полнено)

- **�?олно�?енная админ-панел�?** (Phase 1-5)
  - Backend `/api/v1/admin/*`: auth (TOTP onboarding с QR, login,
  device approval, step-up, refresh, logout), dashboard,
  tracks/users/complaints (без inline SQL), tasks (lyrics_jobs +
  compute_jobs + Taskiq queues + worker audit), logs (Loki proxy), metrics
  (Prometheus proxy), system (services health, containers,
  migrations, feature flags на app_settings), audit
  (admin_actions_log + CSV export), security (login attempts,
  locked users, lockout release), WebSocket для realtime
  - �?ного�?�?овневая за�?и�?а: admin TOTP + device binding +
  pending_device email-flow + step-up для к�?и�?и�?н�?�? дейс�?вий +
  Telegram-але�?�?�? + ко�?о�?кие 15-мин сессии + rotating refresh +
  CSRF double-submit + с�?�?огий CSP + brute-force lockout
  - Observability: Prometheus + Grafana + Loki + Tempo +
  cAdvisor �?е�?ез `docker-compose.observability.yml`,
  `app/core/observability.py` (metrics/tracing/Sentry с PII-�?ил�?�?�?ом),
  �?ас�?и�?енн�?й `/health/deep` (db/redis/s3/taskiq/loki/prometheus)
  - Frontend `frontend/src/admin/` как chunked secure bundle:
  AdminApp, routes, layout, recharts г�?а�?ики, TanStack
  Query/Table, Zustand stores, semantic state-tokens �?ол�?ко
  для StatusPill (см. design-system.md)
  - �?ок�?мен�?а�?ия: `docs/admin/{README,security,onboarding,testing,nginx-example.conf}`
- UX (2026-04): `AdminPromptProvider` (модалки вмес�?о `alert`/`confirm`),
i18n для с�?�?ок админки, динами�?еский заголовок �?аздела в topbar,
в�?движное мен�? на «�?зком» в�?�?по�?�?е (�?�720px), со�?�?и�?овка колонок
в `DataTable` на Users/Tracks/Tasks/Artists/queues
- Post-ingest �?он: enqueue compute + lyrics cascade п�?и новом �?�?еке
(upload / SC import / telegram import); массов�?й SC �?? paced lyrics
без д�?бля; админ Tasks �?? �?абли�?а compute + ис�?о�?ник lyrics job
�?? 2026-04
- �?е�?енес�?и admin-security policy в PrivateCore (см. в�?�?е)
- WebAuthn/Passkey как оп�?ионал�?н�?й в�?о�?ой �?ак�?о�?

## �?езопаснос�?�?

- Scoped JWT для internal-token (bot_player, 15 мин TTL)
- IP whitelist + rate limit на internal endpoints
- hmac.compare_digest для secret comparison
- А�?дио sanitization �?е�?ез FFmpeg пе�?екоди�?ование (payload �?ни�?�?ожае�?ся)
- А�?ди�?-лог в�?одов �?е�?ез бо�?а (�?ас�?и�?и�?�? login_history)
- Rate limit �?�?нинг под production наг�?�?зк�?
- **�?л�?бокая валида�?ия заг�?�?зок (Layer 1)**
  - `python-magic-bin` для п�?ове�?ки magic bytes (`file_validator.py`)
  - �?н�?ег�?а�?ия в audio upload, cover upload, video upload
  - �?ап�?е�? двойн�?�? �?ас�?и�?ений (`.exe`, `.bat`, `.cmd` и д�?.)
- **Sanitization изоб�?ажений (Layer 2)**
  - Pillow re-encode для обложек и ава�?а�?ов (�?е�?ез `media_service.process_image`)
- [~] **Скани�?ование заг�?�?зок: �?ежим `lightweight` �?�?�? `clamav`**
  - �?он�?иг `upload_malware_scan_mode: none | lightweight | clamav` в `config.py`
  - `scan_service.py` stub (ScanResult, scan_bytes)
  - �?ок�?мен�?и�?овано в `.env.example` с �?екоменда�?иями по VPS
  - Реализа�?ия `lightweight` �?ежима (YARA + эв�?ис�?ики, PrivateCore)
  - Реализа�?ия `clamav` �?ежима (clamd TCP/socket, quarantine flow)
  - Раздели�?�? слои: сигна�?�?�?�?/эв�?ис�?ики/по�?оги в PrivateCore, clamd/quarantine orchestration в Backend
- **CSP и изоля�?ия (Layer 4)**
  - `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff` на все о�?ве�?�?
  - `Content-Security-Policy: default-src 'none'` на медиа-о�?ве�?�?

## �?�?ани�?а Backend / PrivateCore

- **�?лейлис�? «�?�?бо�? пол�?зова�?елей» + �?�?�?�? `play_count` (2026-04-27):**
PrivateCore `playcount_policy` (qualify, `rank_user_choice_tracks`);
`GET /api/v1/recommendations/user-choice`, сек�?ия `user_choice` в
`GET /api/v1/recommendations/home`; `PublicPlayCountService` + Redis
24h-дед�?п; залогиненн�?е �?? сигнал listen; гос�?�? �?? `POST /api/v1/tracks/{id}/play`
- **Рекоменда�?ии (2026-04 / RU-first для все�?):**
`recommendation_language_policy` �?? `RU_STRATIFICATION_ALWAYS`,
`DEFAULT_CYRILLIC_STRATA_RATIO`, cold-start affinity;
`_merge_language_affinity` / по�?ожие / fallback home / user-choice �??
с�?�?а�?и�?и�?и�?ованн�?е п�?л�?; см. `docs/private-boundary-inventory.md`
- **Recsys �?? Track A / Phase 1 (2026-04):** гиб�?ид
`genre_samples` + о�?е�?ед�? 15s п�?ев�?�?, `GET .../preview-queue`,
track-preview сегмен�?, админ-CRUD и capability
`recsys.genre_samples.manage`
- **Recsys �?? Track B1 / Phase 5 Backend (2026-04):**
миг�?а�?ия `0060` (�?абли�?�? features/similarity), internal API
`/api/v1/internal/compute/*` (HMAC), `compute_results_router`,
post-upload enqueue, CLI `python -m app.cli.compute_backfill`,
`track_features_builder` + �?ес�?�?
- **Recsys handoff (2026-04-27):** �?дал�?н ка�?алог
`docs/recsys-parallel/`; сс�?лка в `project_context` �?б�?ана; �?ес�?
`test_backfill_dry_run_uses_patched_session` �?ини�? па�?�?
`AsyncSessionLocal` в `app.cli.compute_backfill`
- **Immediate: пе�?енес�?и auth/email policy в PrivateCore**
  - `account_linking_service`: `_LINK_TTL`, `_LINK_EMAIL_TYPE`, `_LINK_PREFIX`, `_LINK_TG_PREFIX`
  - `account_linking_service`: импо�?�?и�?ова�?�? `is_disposable_email` из `dotsound_private_core.services.abuse`
  - `email_auth_service`: `_2FA_SESSION_TTL`, `_MAGIC_LINK_TYPE`, `_2FA_SESSION_TYPE`, `_ML_PREFIX`
  - `email_auth_service`: policy гене�?а�?ии fallback OTP (6-зна�?н�?й код) пе�?енес�?и в helper PrivateCore
  - `email_sender`: �?екс�? TTL fallback-кода с�?�?ои�?�? о�? `FALLBACK_CODE_TTL`, без hardcoded `5 minutes`
- **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - �?е�?енес�?н inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` дос�?�?пн�? �?е�?ез `AdminRepository`/admin endpoints
- **�?е�?енес�?и admin-security policy в PrivateCore**
  - Создан `dotsound_private_core/services/admin_security_policy.py`
  с конс�?ан�?ами и decision-�?�?нк�?иями
  - Удал�?н в�?еменн�?й stub `app/core/_admin_security_constants.py`
  - �?се backend мод�?ли (admin_auth_service, admin_device_service,
  admin_alert_service, admin_manifest_service, ws.py, observability.py)
  пе�?екл�?�?ен�? на импо�?�? из PrivateCore
  - �?обавлен endpoint-кон�?�?ак�? `ADMIN_ALERT_ENDPOINT` в
  `dotsound_private_core/contracts/internal_api.py` + URL builder
  `admin_alert_url` в `internal_bridge.py`
  - Реализован `handle_admin_alert` в DotSoundBot
  (`bot/api/internal.py`) с allowlist `chat_id` и HTML-escape
  - Тес�?�?: PrivateCore 88 admin-related, Bot 9 admin alert,
  Backend smoke + repo

## �?�?од�?к�?: пя�?�? сп�?ин�?ов (�?еализовано в Backend, 2026-04)

- S1 **Radio** �?? `GET /api/v1/tracks/{id}/radio` (ка�?алог + YouTube mix/search + materialize), �?лаги `RADIO_*` в `config`, поли�?ика `dotsound_private_core.services.radio_policy`
- S2 **Co-listen** �?? `co_listen_rooms` + `POST/GET/PATCH /api/v1/colisten/rooms`, `WS /api/v1/colisten/ws/{room_id}` (Redis pub/sub), `dotsound_private_core.services.colisten_policy`
- S3 **Author stats** �?? `GET /api/v1/tracks/{id}/author-stats` (владеле�?), `listen_events` + `play_count` + лайки, `author_stats_policy` (ок�?�?гление)
- S4 **�?лейлис�?�? коллаб** �?? `playlist_collaborators`, `playlist_invite_tokens`, `POST /playlists/{id}/invites`, `POST /playlists/invites/accept`, п�?авка `PlaylistService` для **editor** коллаб
- S5 **Сниппе�?�?** �?? `track_snippets`, `POST /tracks/{id}/snippets`, `snippet_worker` (Taskiq + ffmpeg), `snippet_policy` + gating `catalog_type`
- **Follow-up:** Mini App / бо�? (кнопки radio, colisten, UI с�?а�?ис�?ики, accept invite), e2e-�?ес�?�?, Prometheus-ме�?�?ики `radio_*` / runbook; �?�?иди�?еский sign-off third-party + сниппе�?ов (см. `LEGAL.md`). �?иг�?а�?ия: `alembic upgrade 0056`.

## �?лее�? в бо�?е

- Inline а�?дио-плее�? (3 �?�?ека, editMessageMedia)
- �?�?бо�? ис�?о�?ника: �?ои / �?айки / �?ен�?а
- file_id кэ�? в Redis
- �?�?едзаг�?�?зка след�?�?�?ей па�?ки
- Фил�?�?�?а�?ия �?�?еков без �?айлов (playable_only)
- Рас�?и�?и�?�? ис�?о�?ники: плейлис�?�?, подписки, �?екоменда�?ии
  - �?ля ис�?о�?ника "�?екоменда�?ии": алго�?и�?м �?анжи�?ования и ско�?инг в PrivateCore, Backend/бо�? �?? адап�?е�?�? в�?да�?и
- Shuffle / Random �?ежим

## �?н�?е�?на�?ионализа�?ия (i18n)

- **Английская ве�?сия сай�?а (базовая)**
  - `react-i18next` + `i18next-browser-languagedetector`
  - JSON-ка�?алоги `ru.json` / `en.json` (кл�?�?ев�?е эк�?ан�?: Auth, Home, Nav, Search, Liked, Upload, Profile, Playlists, Settings)
  - Telegram `language_code` custom detector
  - �?е�?екл�?�?а�?ел�? яз�?ка в SettingsSheet
  - �?оле `locale` в модели User + PATCH /users/me
  - Alembic миг�?а�?ия `0024`
- i18n: миг�?и�?ова�?�? ос�?ав�?иеся ~35 .tsx �?айлов на `useTranslation`

## Эквалайзе�?

- 8-полосн�?й Web Audio EQ (32 Hz -- 16 kHz)
- Preset-сис�?ема
- Се�?ве�?ная син�?�?ониза�?ия нас�?�?оек (`GET/PUT /api/v1/users/me/eq`)
- **Ул�?�?�?ения эквалайзе�?а (v2)**
  - �?а�?аме�?�?и�?еский Q-factor (�?и�?ина полос�?) на каждой полосе
  - �?из�?ализа�?ия АЧХ в �?еал�?ном в�?емени (canvas/SVG)
  - �?ополни�?ел�?н�?е п�?есе�?�?: Bass Boost, Vocal, Classical, Electronic
- **�?�?одвин�?�?ая об�?або�?ка (v3)**
  - Compressor/Limiter (`DynamicsCompressorNode`)
  - Stereo Balance / Pan
  - Loudness normalization

## PWA / Фонов�?й плее�?

- Ус�?ановка на �?с�?�?ойс�?во: `isTelegram()` по `initData` / user; `InstallPrompt` (iOS Safari / п�?о�?ий iOS, Chromium `beforeinstallprompt`, fallback без BIP); manifest `id`, один `link` manifest
- Media Session API (lock-screen кон�?�?оли: play/pause/next/prev/seekto)
- �?�?а�?зе�?ная ве�?сия с email auth + Telegram code auth
- **PWA-слой пове�?�? �?ек�?�?его SPA**
  - `manifest.json` �?е�?ез `vite-plugin-pwa` (name, icons SVG, standalone, theme_color)
  - Service Worker: `NetworkFirst` для API, `CacheFirst` для с�?а�?ики
  - �?конки: 192x192 и 512x512 SVG в `frontend/public/`
  - Meta-�?еги: theme-color, apple-touch-icon, apple-mobile-web-app-capable
- Picture-in-Picture для видео-�?�?еков
  - `video.requestPictureInPicture()` в `TrackCardSheet.tsx`
- **Offline-кэ�? �?�?еков (со�?�?анение для о�?�?лайн-п�?осл�?�?ивания)**
  - **Со�?�?анение**: кнопка "Ска�?а�?�?" на TrackCardSheet; а�?дио ке�?и�?�?е�?ся в Cache API (`caches.open('offline-tracks')`)
  - **Х�?анили�?е**: IndexedDB для ме�?аданн�?�? (track JSON, обложка blob, с�?а�?�?с); Cache API для а�?дио�?айлов
  - **Уп�?авление**: эк�?ан "Ска�?анн�?е" (список, заня�?о мес�?а, кнопка �?даления); лими�? по об�?�?м�? (нас�?�?аиваем�?й, ~500MB)
  - **�?�?�?лайн-�?ежим**: Service Worker пе�?е�?ва�?�?вае�? `/api/v1/tracks/{id}/audio` и `/hls/` �?? если ес�?�? в ке�?е, о�?да�?�? локал�?но
  - **�?лее�?**: `playTrack()` п�?ове�?яе�? Cache API пе�?ед се�?ев�?м зап�?осом; о�?�?лайн-�?�?еки иг�?а�?�? без ин�?е�?не�?а
  - **Син�?�?ониза�?ия**: п�?и появлении се�?и �?? sync play counts (Background Sync API); обновление ме�?аданн�?�?
  - **�?г�?ани�?ения**: HLS-�?�?еки ке�?и�?ова�?�? как один �?айл �?е�?ез fallback endpoint `/audio`; DRM/ли�?ензи�?ование не п�?именяе�?ся (UGC-пла�?�?о�?ма)
- **�?�?амо�?н�?й един�?й плее�? для �?азн�?�? пла�?�?о�?м / ис�?о�?ников**
  - �?�?ивес�?и к едином�? UX `ugc`, `licensed`, `external_reference`
  - Раздели�?�? `access_mode`: `internal_stream`, `third_party_stream`, `official_embed`, `external_link`
  - �?оказа�?�? пол�?зова�?ел�? поня�?н�?й �?ежим дос�?�?па: на�? с�?�?им / вне�?ний по�?ок / о�?к�?�?�?�? ис�?о�?ник
  - �?ля каждого ис�?о�?ника оп�?едели�?�? доп�?с�?им�?�? ме�?аник�? playback и ог�?ани�?ения по Terms
  - �?а�?монизи�?ова�?�? `PlayerContext`, `TrackCard`, `TrackCardSheet`, deep links и search/import UX
  - Не сме�?ива�?�? в UI вне�?ний reference и вн�?�?�?енний storage-backed �?�?ек как один и �?о�? же �?ип восп�?оизведения

## �?идео к �?�?екам

- �?аг�?�?зка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- Удаление видео (`DELETE /tracks/{id}/video`)
- �?�?да�?а видео (`GET /tracks/{id}/video`, proxy из S3)
- UI: �?оновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- **�?п�?имиза�?ия/сжа�?ие видео**
  - Taskiq task `transcode_video` (`video_transcoding.py`): FFmpeg H.264 + AAC
  - Max 720p, CRF 23, `-preset medium`, `-movflags +faststart`
  - Thumbnail гене�?а�?ия (FFmpeg `-ss 1 -frames:v 1`)
  - `video_processing_status` + `video_thumbnail_key` на Track (миг�?а�?ия `0023`)
  - Upload -> temp S3 -> queue -> async transcode -> update status
- Увели�?и�?�? лими�? заг�?�?зки до 50MB (из PrivateCore `MAX_VIDEO_BYTES`)
- Адап�?ивн�?й HLS для видео (как для а�?дио)
- �?г�?ани�?ение дли�?ел�?нос�?и видео (Canvas-с�?ил�? или длина �?�?ека)
- У�?�?�? видео в storage quota пол�?зова�?еля

## �?е�?аданн�?е �?�?ека

- �?зменение `is_public` после заг�?�?зки (PATCH)
- �?аг�?�?зка/замена обложки
- �?аг�?�?зка/�?даление видео
- Текс�? песни (plain text) + син�?�?онизи�?ованн�?е �?айм-код�?
- **Редак�?и�?ование title, artist, genre после заг�?�?зки**
  - `TrackUpdateRequest` �?ас�?и�?ен (Optional поля title/artist/genre/description)
  - `TrackRepository.update_track()` + `TrackService.update_track()`
  - PATCH endpoint обновл�?н: п�?инимае�? л�?б�?�? комбина�?и�? полей
- �?оле `description` в модели Track (TEXT, nullable)
  - Alembic миг�?а�?ия `651109411149`
- **Ав�?ооп�?еделение �?екс�?а песен (lyrics auto-detection)**
  - �?ес�? пайплайн в PrivateCore (�?�?�?ная ко�?обка)
  - Backend: �?онкий адап�?е�? (S3 download, в�?зов PrivateCore, со�?�?анение в �?�?)
  - �?�?бо�? �?ежима: "�?п�?едели�?�? �?екс�?" (без �?аймкодов) / "�?п�?едели�?�? �?екс�? + �?аймкод�?"
  - �?е�? �?аймкодов: synced_lines �?�?аня�?ся в �?�?, пе�?екл�?�?ение без пе�?ес�?�?�?а
  - Редак�?и�?ование ав�?осгене�?и�?ованного �?екс�?а, source manual/auto
  - �?одде�?жка вне�?ни�? �?�?еков без а�?дио (�?ол�?ко �?екс�?)
  - �?иг�?а�?ия 0030: колонка source в track_lyrics
  - Taskiq-зада�?а generate_lyrics_task
  - API: POST /lyrics/auto, GET /lyrics/auto/status
  - Frontend: кнопки ав�?огене�?а�?ии, toggle �?аймкодов, i18n
  - Re-define fix: админ-кнопки с `bypass_cache=true` + �?ас�?и�?енн�?е debug-логи в ка�?�?о�?ке (�?ес�?е�?�?нка)
  - Search fallback fix: п�?и miss по `(artist,title)` делаем retry по `title-only` и со�?�?аняем cache alias
  - Stability fix (2026-04-25): remote catalog-align �?епе�?�? пол�?�?ае�? `audio_seconds` о�? compute-worker для ко�?�?ек�?ной �?кал�? в�?емени; добавлен за�?и�?н�?й rescue о�? с�?лопн�?�?ой line-sync �?аймлинии (когда с�?�?оки п�?илипа�?�? к одном�? позднем�? яко�?�?), пл�?с retry на о�?п�?авк�? `result/fail` из worker.
- **Auto-lyrics: в�?нос �?яж�?лой об�?або�?ки на вне�?ний GPU-се�?вис (дал�?кое б�?д�?�?ее)**
  - �?�?дел�?н�?й се�?ве�?/се�?вис с GPU для об�?або�?ки а�?дио
  - Backend о�?п�?авляе�? а�?дио�?айл во вн�?�?�?енний API PrivateCore,
  а PrivateCore �?же сам �?е�?ае�?, об�?аба�?�?ва�?�? локал�?но или в�?з�?ва�?�? вне�?ний GPU-се�?вис
  - �?н�?ег�?а�?ия �?е�?ез с�?�?ес�?в�?�?�?ий `lyrics_provider` в PrivateCore (вне�?ние де�?али �?? вн�?�?�?и �?�?�?ного я�?ика)
- **Karaoke после catalog + remote ASR align (пока не делаем):**
UI показ�?вае�? �?ежим «�?а�?аоке» �?ол�?ко п�?и `word_times` на с�?�?ока�?
**и** `sync_quality === "word"` (`LyricsPanel.tsx`, `FullscreenLyrics.tsx`).
�?е�?ка `POST .../audio-compute/.../result` с
`align_text_to_precomputed_asr_timed_words` сей�?ас пи�?е�? в �?�?
**�?ол�?ко** line-level с�?�?оки + `sync_quality=line` �?? словесн�?е
�?аймкод�? с во�?ке�?а в со�?�?ан�?нн�?й JSON не пе�?енося�?ся. На б�?д�?�?ее:
после align п�?иклеи�?�?/�?асп�?едели�?�? `word_times` к в�?�?овненн�?м
с�?�?окам ка�?алога (из `asr_timed_words` или ис�?одн�?�?
`synced_lines` во�?ке�?а) и п�?и �?спе�?е в�?с�?авля�?�? `word`, �?�?об�?
ка�?аоке снова �?або�?ал п�?и э�?алонном �?екс�?е.
- Теги (`tags`, JSONB или о�?дел�?ная �?абли�?а)
- BPM auto-detection (background task, `librosa` / `essentia`)
  - �?звле�?ение �?и�?/по�?оги confidence и decision rules в PrivateCore, Taskiq orchestration и запис�? �?ез�?л�?�?а�?а �?? в Backend
- Waveform generation (pre-render �?о�?м�? волн�? для UI)

## Ча�? и коммен�?а�?ии

- Ча�?: DM, г�?�?пп�?, WebSocket real-time
- Реак�?ии, вложения, голосов�?е сооб�?ения, �?и�?�?ование
- WebSocket: Redis pub/sub, presence, typing indicators
- �?оммен�?а�?ии к �?�?екам: CRUD, голосование, пин, ск�?�?�?ие;
Mini App �?? сек�?ия в `TrackCardSheet` для п�?бли�?н�?�? �?�?еков;
се�?вис �?? коммен�?а�?ии недос�?�?пн�? п�?и `is_public=false`;
о�?ве�?�? на коммен�?а�?ии (`parent_id`, де�?ево вложеннос�?и)
- [x] In-app �?ведомления: лайк коммен�?а�?ия и о�?ве�? (`comment_like`,
  `comment_reply`), пе�?е�?од из панели �?ведомлений к коммен�?а�?и�?
  (`focus_comment_id`, подсве�?ка ве�?ки) �?? 2026-04
- [~] �?о�?або�?ки �?а�?а (обс�?ди�?�? о�?дел�?но)

## �?а�?�?о�?ка а�?�?ис�?а (multi-source)

- [x] **�?а�?алог диског�?а�?ии (SoundCloud) �?? phase 1:** миг�?а�?ия
  `0063` �?? `artist_catalog_releases`, `artist_catalog_release_tracks`,
  `artists.soundcloud_user_id`, `artists.soundcloud_permalink`;
  SQLAlchemy-модели; без HTTP/синка (след. э�?ап�? 2�??3)
- [x] **�?а�?алог диског�?а�?ии �?? phase 2:** `SoundCloudService.list_user_albums`
  (пагина�?ия `next_href`), `fetch_track_by_id`, `expand_playlist_stub_tracks`,
  `ensure_soundcloud_ids_for_artist` + `ArtistRepository.find_by_soundcloud_user_id`;
  без Taskiq / о�?кес�?�?а�?о�?а ка�?алога (phase 3)
- [x] **�?а�?алог диског�?а�?ии �?? phase 3:** `ArtistCatalogSyncService`
  (`sync_full_artist`, `sync_single_release`), `ArtistCatalogRepository`,
  Taskiq `artist_catalog_sync_worker` (`sync_artist_catalog_task`,
  `sync_artist_catalog_release_task`), `catalog_uploader_id`,
  `SoundCloudService.fetch_playlist_by_id` / `download_artwork_as_cover_key`;
  без п�?бли�?н�?�?/admin HTTP-�?о�?�?ов (phase 4�??6); пе�?ед синком �??
  `try_autofill_soundcloud_user_id_for_artist` (permalink / п�?о�?ил�?н�?е URL
  из `source_profiles`, ина�?е пе�?в�?й �?и�? user search) �?? 2026-04-28;
  �?о�? же autofill в�?з�?вае�?ся из `AdminArtistCatalogService` п�?и пос�?ановке
  full/release sync в о�?е�?ед�? (�?ан�?�?е enqueue о�?секал `NULL` до во�?ке�?а)
  �?? 2026-04-29
- [x] **�?а�?алог диског�?а�?ии �?? phase 4:** п�?бли�?ное �?�?ение ка�?алога
  `GET /api/v1/artists/{id}/catalog/releases`,
  `GET /api/v1/artists/{id}/catalog/releases/{release_id}` �??
  `ArtistCatalogReadService`, �?ас�?и�?ение `ArtistCatalogRepository`,
  с�?ем�? `app/schemas/artist_catalog.py`, pytest
  `tests/app/api/v1/test_artist_catalog_releases.py`;
  admin ка�?алог: `app/api/v1/admin/artist_catalog.py`,
  `tests/app/api/v1/admin/test_admin_artist_catalog.py`
- [x] **�?а�?алог диског�?а�?ии �?? phase 5 (mini app):** ка�?�?о�?ки �?елизов и
  эк�?ан �?елиза с ordered track list в `ArtistView`, API-клиен�? и �?ип�?;
  восп�?оизведение �?е�?ез `TrackList` / `TrackCard` �?? 2026-04-28
- [x] **�?а�?алог диског�?а�?ии �?? phase 7:** `catalog_sync_policy` (PrivateCore),
  лими�?�? в `ArtistCatalogSyncService`, cooldown пос�?ановки в о�?е�?ед�? в
  `AdminArtistCatalogService` + 429 в admin API,
  `ArtistCatalogRepository.latest_synced_at_for_artist`,
  `SoundCloudService.list_user_albums` �?? `(albums, truncated)` �?? 2026-04-28
- Policy-exception для явного source attribution
(`source_name` + `source_page_url`) за�?икси�?ован в
`docs/ai-boundary-policy.md` (Backend + PrivateCore)
- PrivateCore: �?ас�?и�?ен кон�?�?ак�? `ArtistInfo` полями
`source_profiles`, `primary_source_id`, `discography`
- Backend: добавлен�? `artists.source_profiles` (JSON) и
`artists.primary_source_id` (миг�?а�?ия `0039`)
- Backend API: `ArtistDetailResponse` и `/api/v1/artists/{id}`
возв�?а�?а�?�? `source_profiles` и `primary_source_id`
- Frontend ArtistView: го�?изон�?ал�?н�?й пе�?екл�?�?а�?ел�? ис�?о�?ников
под ава�?а�?ом + �?енде�? bio/meta/discography по в�?б�?анном�? ис�?о�?ник�?
- Frontend ArtistView: полноэк�?анн�?й п�?осмо�?�? ава�?а�?ки с
зак�?�?�?ием по overlay / кнопке / `Esc`
- Frontend ArtistView: о�?дел�?ная с�?�?ока
`�?с�?о�?ник: <source_name>` с кликабел�?ной сс�?лкой на с�?�?ани�?�?
ис�?о�?ника
- Рег�?ессионн�?е �?ес�?�? обновлен�?:
  - PrivateCore `test_artist_info_provider.py`
  - Backend `test_artist_enrichment_service.py`,
  `test_artist_enrich.py`, `test_artist.py`

## �?�?едзаг�?�?зка �?�?еков

- �?�?едзаг�?�?зка след�?�?�?ей па�?ки в бо�?е (DotSoundBot)
- `GET /tracks/{id}/adjacent` (sequential/shuffle/repeat_one)
- hls.js с ABR (`startLevel: -1`, `enableWorker: true`)
- **Prefetch в Mini App / б�?а�?зе�?е (ме�?аданн�?е)**
  - `GET /tracks/{id}/queue?count=3` -- нов�?й endpoint
  - `TrackRepository.get_next_tracks()` возв�?а�?ае�? N след�?�?�?и�? �?�?еков
  - �?е�? в `PlayerContext` �?е�?ез `useRef` (`prefetchCacheRef`)
  - `playNext` испол�?з�?е�? ке�?, fallback на `getAdjacentTracks`
- **�?�?едзаг�?�?зка а�?дио след�?�?�?его �?�?ека (gapless)**
  - �?�?и п�?оиг�?�?вании �?ек�?�?его �?�?ека �?? на�?ина�?�? б�?�?е�?иза�?и�? а�?дио след�?�?�?его �?�?ека в �?оне
  - Ск�?�?�?�?й `<audio>` элемен�? (`preloadAudioRef`) с `preload="auto"` заг�?�?жае�? URL след�?�?�?его �?�?ека
  - �?ля HLS: созда�?�? в�?о�?ой `Hls` instance, п�?ивяза�?�? к preload-элемен�?�?, дожда�?�?ся `MANIFEST_PARSED`
  - �?�?и `playNext` �?? swap: preload-элемен�? с�?анови�?ся основн�?м, мгновенн�?й с�?а�?�? без б�?�?е�?иза�?ии
  - �?ап�?ск п�?едзаг�?�?зки по по�?ог�? (нап�?име�?, �?ек�?�?ий �?�?ек п�?оиг�?ан на 75% или ос�?алос�? < 30 сек)
  - �?�?мена п�?едзаг�?�?зки п�?и �?�?�?ном пе�?екл�?�?ении на д�?�?гой �?�?ек
  - �?г�?ани�?ение: п�?едзаг�?�?жа�?�? �?ол�?ко 1 след�?�?�?ий �?�?ек (экономия �?�?а�?ика)

## �?ден�?и�?ика�?ия заг�?�?з�?ика

- `uploaded_by_id` на Track (FK -> User с telegram_id)
- `created_at` / `updated_at` timestamps
- `RequestLoggingMiddleware` логи�?�?е�? `client_ip` в structlog
- **Рас�?и�?енн�?е ме�?аданн�?е заг�?�?зки (admin-only)**
  - �?одел�? `TrackUploadMeta` (миг�?а�?ия `0022`): `upload_ip`, `upload_user_agent`, `upload_telegram_data` (JSON)
  - �?аполнение п�?и upload из `request.client.host` + headers
  - Admin endpoint `GET /admin/tracks/{id}/upload-meta`
  - PrivateCore: `UPLOAD_META_RETENTION_DAYS = 90`
- Taskiq job для ав�?о�?даления meta с�?а�?�?е retention (GDPR)

## Удаление акка�?н�?а

- **Soft delete с grace period (30 дней)**
  - `DELETE /api/v1/users/me` (body: `{"confirmation": "DELETE"}`)
  - `POST /api/v1/users/me/restore` -- восс�?ановление в grace period
  - `deleted_at` на User (миг�?а�?ия `0021`)
  - PrivateCore: `account_deletion_policy.py` (GRACE_PERIOD_DAYS, is_within_grace_period, is_valid_confirmation)
  - Auth flow: soft-deleted пол�?зова�?ели в grace period п�?о�?одя�? auth
- [x] Taskiq job для hard delete после 30 дней — `app/services/account_deletion_service.py` + `account_deletion_worker.py`, миграция `0078_user_hard_delete_anonymize_fks` (`messages.sender_id`, `track_comments.user_id` CASCADE → SET NULL), seed `daily-user-hard-delete` cron `30 3 * * *`; PrivateCore policy: `hard_delete_cutoff`, `build_anonymized_username`, `ANONYMIZED_DISPLAY_NAME`, `HARD_DELETE_BATCH_LIMIT`; комментарии и сообщения рендерятся как `Deleted user`; tests: PrivateCore +6, Backend +6 (2026-05-06).
- **�?оли�?ика �?даления данн�?�?**
  - �?�?о�?ил�?, ава�?а�?, нас�?�?ойки EQ -- �?дали�?�?
  - �?айки, дизлайки, подписки -- �?дали�?�?
  - Сооб�?ения в �?а�?а�? -- анонимизи�?ова�?�? ("Deleted User")
  - �?оммен�?а�?ии -- анонимизи�?ова�?�?
  - �?лейлис�?�? -- �?дали�?�?
  - Т�?еки -- в�?бо�? пол�?зова�?еля: �?дали�?�? или ос�?ави�?�? анонимно
  - S3 об�?ек�?�? -- �?дали�?�? п�?и �?далении �?�?ека
- **�?од�?ве�?ждение �?даления**
  - �?ов�?о�?ная ав�?о�?иза�?ия
  - Текс�?овое под�?ве�?ждение ("DELETE")
  - Email/Telegram �?ведомление
  - �?оли�?ик�? re-auth/cooldown/max-attempts для �?даления �?�?ани�?�? в PrivateCore

## Frontend / Mini App

- [x] �?лее�? / ка�?�?о�?ка �?�?ека / ове�?леи: motion-�?окен�?, decay спек�?�?а п�?и
  па�?зе, enter/exit (в �?.�?. FullscreenLyrics), мик�?о-виз в `PlayerBar` �??
  2026-04-29
- [x] С�?�?ани�?а 404: кон�?�?ас�? CTA, ка�?�?о�?ка, safe-area / адап�?ив �?? 2026-04-29
- **�?ок�?�?�?ие Backend API клиен�?ом:** инвен�?а�?�? и п�?ио�?и�?е�?�? �??
`docs/api-frontend-coverage.md`; �?ас�?и�?ен `frontend/src/lib/api.ts`,
исп�?авлен `POST /users/me/avatar`, UI (OAuth disconnect, �?даление акка�?н�?а,
по�?ожие а�?�?ис�?�?), `adminApi.metricInstant`; �?ег�?ессия �??
`scripts/check_openapi_frontend_coverage.py`
- �?лавная: CTA «Сл�?�?а�?�?/Play» �?? с�?а�?�? с пе�?вого �?�?ека плейлис�?а дня
(дал�?�?е �?? с�?�?ес�?в�?�?�?ий radio-prefetch в `PlayerContext`); ка�?�?о�?ка
«плейлис�? недели» и эк�?ан `/weekly-mix` (API `weekly-playlist`).
- �?осс�?ановление пози�?ии восп�?оизведения п�?и пе�?езап�?ске
- �?оно�?�?ом-�?ил�?�?�? в нас�?�?ойка�?
- Админ-панел�?: �?п�?авление пол�?зова�?елями
  - �?сли добавя�?ся бан�?/risk flags/anti-abuse actions, decision rules и по�?оги должн�? ид�?и из PrivateCore
- Админ-панел�?: моде�?а�?ия кон�?ен�?а
  - �?о�?оги auto-hide/escalation и moderation policy де�?жа�?�? в PrivateCore, панел�? �?? UI + в�?зов�? Backend API
- Админ-панел�?: �?п�?авление бэкапами (см. в�?�?е)

## Frontend оп�?имиза�?ия

- **Mini App (б�?а�?зе�?): GPU / компози�?о�?** �?? смяг�?ен�? �?окен�? с�?екла,
�?икс-панели `#nav` / `#player-bar` на `--glass-backdrop-fixed*`,
липкий поиск на более л�?гком blur; класс `ds-low-glass` п�?и
`prefers-reduced-motion` / `prefers-reduced-data`; без бесконе�?н�?�?
splash/home; п�?и play �?? л�?гкий `pbPlayGlow` (о�?кл. п�?и reduce motion),
с�?а�?и�?н�?й EQ в о�?е�?еди; спек�?�? на canvas ~12 fps, cap DPR, мен�?�?е
с�?олб�?ов �?? 2026-04
- **Waveform (ка�?�?о�?ка �?�?ека): снижение наг�?�?зки на iGPU** �??
`setInterval` ~12 fps вмес�?о RAF на �?ас�?о�?е дисплея; б�?�?е�? FFT без
аллока�?ий кажд�?й кад�?
- **PlayerContext: CPU** �?? throttling обновлений `currentTime` в React
(~10/s), flush п�?и play/pause/seek/skip; в�?�?�?и и эк�?ан�? без �?айме�?а
пе�?еведен�? с `usePlayer()` на `usePlayerActions` / `usePlayerMeta`, �?�?об�?
не пе�?е�?исов�?ва�?�?ся на кажд�?й �?ик
- **SearchView: п�?ог�?ессивная в�?да�?а** �?? `getTracks` / `searchSuggest`
не жд�?�? YouTube, Bandcamp, SoundCloud; вне�?ние сек�?ии обновля�?�?ся
по ме�?е о�?ве�?а и мог�?�? о�?об�?ажа�?�?ся до го�?овнос�?и блока «На пла�?�?о�?ме»
- **PlayerContext split (п�?оизводи�?ел�?нос�?�?)**
  - 3 кон�?екс�?а: `PlayerStateCtx` (currentTime, duration, isPlaying),
  `PlayerActionsCtx` (с�?абил�?н�?е callbacks �?е�?ез useCallback),
  `PlayerMetaCtx` (track, volume, EQ, модалки)
  - 3 �?�?ка: `usePlayerState()`, `usePlayerActions()`, `usePlayerMeta()`
  - `usePlayer()` -- compat shim для плавной миг�?а�?ии
- **LikesContext оп�?имиза�?ия**
  - `useMemo` на value, `useCallback` на все �?�?нк�?ии
- **React Router (deep links, PWA)**
  - `react-router-dom` v7 (React Router)
  - �?а�?�?�?�?�?�?: `/`, `/search`, `/upload`, `/liked`, `/playlists`,
  `/chats`, `/chats/:id`, `/profile`, `/track/:trackId`
  - `BottomNav` �?е�?ез `useNavigate` + `useLocation`
  - `BrowserRouter basename="/mini_app"`
  - Browser back/forward, shareable URLs, deep links
- **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView, LikedView, PlaylistsView, ChatsView, ProfileView
  - `hls.js` в о�?дел�?н�?й chunk (`manualChunks`)
  - `<Suspense>` об�?�?�?ка для route-level lazy loading
- **TanStack Query (API ке�?и�?ование)**
  - Ав�?ома�?и�?еский ке�?, дед�?плика�?ия, stale-while-revalidate
  - �?ос�?епенное внед�?ение (endpoint за endpoint)
- Типиза�?ия: �?б�?а�?�? 5x `Promise<any>` в `api.ts`
  - `ImportJobResponse` + `ImportAudioInfo` в `types/api.ts`
  - `genre` + `description` добавлен�? в `Track` interface
- CSS: �?ассмо�?�?е�?�? �?азделение `global.css` (~2700 с�?�?ок)

## Backend API

- YouTube import/playback: fallback на auto-в�?бо�? �?о�?ма�?а в
`yt-dlp` п�?и `Requested format is not available` (без 422/503 из-за
ж�?с�?кого format-string)
- YouTube import/playback: fallback по client-п�?о�?илям `yt-dlp`
п�?и anti-bot (`Sign in to confirm you�??re not a bot`) + возв�?а�? 503
вмес�?о 422 для в�?еменной блоки�?овки
- **Elasticsearch (поиск + suggest)**: индекс�? �?�?еков/а�?�?ис�?ов,
Taskiq reindex/backfill, `GET /api/v1/search/suggest`, поиск �?�?еков
с `q` �?е�?ез ES + PG fallback, bool/should (strict + fuzzy) для �?�?еков/а�?�?ис�?ов
и саджес�?а, counter `elasticsearch_query_total` (op/outcome) в `observability`
- `artist_link_backfill_task` / `track_artists`: дед�?п по
`canonical` (PrivateCore + `resolve_and_link`), `ON CONFLICT DO NOTHING`
в `link_track`, `begin_nested` + `error`/`error_type` в backfill
- `LOG_THIRD_PARTY_LEVEL` / `apply_third_party_log_levels` �?? �?�?овен�?
`urllib3`/httpx/ES/SQL-э�?а о�?дел�?но о�? `LOG_LEVEL`; Taskiq во�?ке�?�?
�?оже п�?и с�?а�?�?е
- playable_only �?ил�?�?�? в track listing endpoints
- internal-token endpoint с полной за�?и�?ой
- WebSocket: соб�?�?ие player.state для син�?�?ониза�?ии
- �?агина�?ия liked tracks (backend + frontend)
  - Backend: `page`/`has_more` в `UserLikesResponse`
  - Frontend: `LikedView` с "�?оказа�?�? е�?�?" кнопкой

## Ю�?иди�?еский а�?ди�?: анализ конк�?�?ен�?ов (UGC + с�?. 1253.1)

> **Цел�?**: из�?�?и�?�? кажд�?й се�?вис из списка на 2 ве�?и:
>
> 1. Нали�?ие web-плее�?а / API для с�?�?иминга �?? возможна ли �?е�?�?ансля�?ия
>   а�?дио на DotSound (аналоги�?но SoundCloud: зв�?к пе�?еда�?�?ся
>    пол�?зова�?ел�?, плее�? на�?, м�? оболо�?ка).
> 2. �?оли�?ика, согла�?ения, п�?авовая �?еализа�?ия �?? �?�?о можно
>   адап�?и�?ова�?�? для DotSound (�?екс�?�? о�?е�?�?, дисклейме�?�?,
>    п�?о�?ед�?�?�? takedown, �?о�?м�? заг�?�?зки с под�?ве�?ждением п�?ав).

### �?а�?его�?ия 1: �?�?ям�?е аналоги (UGC + ин�?о�?ма�?ионн�?й пос�?едник)

- **Musify.club**
  - Web-плее�?: ес�?�? ли п�?бли�?н�?й с�?�?им/API, можно ли вс�?�?ои�?�?
  - Ю�?идика: пол�?зова�?ел�?ское согла�?ение (с�?. 1253.1), с�?�?ани�?а
  `/contacts/legal` (пе�?е�?ен�? ли�?ензий с �?�?�? «Адв�?�?�?зик» и д�?.),
  п�?о�?ед�?�?а DMCA/takedown, �?о�?ма заг�?�?зки
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **4beat.ru**
  - Web-плее�?: с�?�?им, embed, API
  - Ю�?идика: пол�?зова�?ел�?ское согла�?ение, �?о�?ма заг�?�?зки �?�?ека
  (какие гало�?ки/под�?ве�?ждения п�?ав �?�?еб�?�?�?), с�?�?ани�?а п�?авооблада�?елям
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **QPlet.ru**
  - Web-плее�?: с�?�?им, п�?бли�?н�?й дос�?�?п к а�?дио
  - Ю�?идика: �?словия заг�?�?зки, онбо�?динг а�?�?ис�?а, о�?е�?�?а
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **Созв�?к (sozvuk.ru)**
  - Web-плее�?: с�?�?им, embed, API для �?�?еков
  - Ю�?идика: п�?бли�?ная о�?е�?�?а (с�?. 1253.1), как о�?о�?млен�? п�?ава
  п�?и заг�?�?зке, поли�?ика �?даления по жалобе
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound

### �?а�?его�?ия 2: �?�?�?пн�?е пла�?�?о�?м�? с UGC-компонен�?ом

- **VK �?�?з�?ка (vk.com/music)**
  - Web-плее�?: зак�?�?�?�?й API, возможнос�?�? �?е�?�?ансля�?ии
  - Ю�?идика: ли�?ензионное согла�?ение (`vk.com/terms/music`),
  Content ID, как �?азделя�?�? ли�?ензи�?ованн�?й и UGC-кон�?ен�?,
  п�?о�?ед�?�?а жалоб
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **Яндекс.�?�?з�?ка**
  - Web-плее�?: зак�?�?�?�?й с�?�?им, �?анжи�?ование UGC vs ли�?ензи�?ованное
  - Ю�?идика: �?словия заг�?�?зки пол�?зова�?ел�?ской м�?з�?ки,
  как UGC показ�?вае�?ся ниже о�?и�?иал�?ного в поиске
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **ZVUK (zvuk.com)**
  - Web-плее�?: с�?�?им, па�?�?н�?�?ская модел�?
  - Ю�?идика: �?словия для а�?�?ис�?ов, догово�?�? с дис�?�?иб�?�?�?о�?ами,
  �?�?ебования к п�?авам
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound

### �?а�?его�?ия 3: Се�?ая зона

- **�?ай�?ев.Н�?Т (zaycev.net)**
  - Web-плее�?: с�?�?им, API, �?ек�?�?ая модел�? (100% ли�?ензии с 2019)
  - Ю�?идика: п�?�?�? о�? UGC к ли�?ензиям �?? �?�?о зас�?авило пе�?ей�?и,
  пол�?зова�?ел�?ское согла�?ение (написано �?�?ис�?ами), с�?�?ани�?а
  п�?авооблада�?елям, п�?о�?ед�?�?а 5-дневного takedown
  - �?�?вод�?: какие �?екс�?�?/п�?о�?ед�?�?�? адап�?и�?ова�?�? для DotSound
- **TRULA-music (trula-music.ru)**
  - Web-плее�?: плее�? + видже�?�? для с�?�?име�?ов
  - Ю�?идика: о�?е�?�?а (с�?. 1253.1), �?зкая ни�?а �?? как о�?о�?мля�?�? п�?ава
  - �?�?вод�?: �?�?о адап�?и�?ова�?�? для DotSound
- **Muzofond.fm / LightAudio.ru / HitMo (ан�?ип�?име�?�?)**
  - Web-плее�?: о�?к�?�?�?�?й с�?�?им, ска�?ивание mp3
  - Ю�?идика: не�? явн�?�? ли�?ензий, сс�?ла�?�?ся на «пол�?зова�?ели
  заг�?�?зили», пе�?иоди�?еские блоки�?овки Роскомнадзо�?а
  - �?�?вод�?: какие о�?ибки Н�? пов�?о�?я�?�?

### �?�?огов�?й о�?�?�?�? (после анализа все�? се�?висов)

- Сводная �?абли�?а: се�?вис / web-API / возможнос�?�? �?е�?�?ансля�?ии /
�?�?иди�?еская модел�? / �?иски / �?�?о адап�?и�?ова�?�?
- Список конк�?е�?н�?�? �?екс�?ов для адап�?а�?ии: о�?е�?�?а, дисклейме�?,
с�?�?ани�?а п�?авооблада�?елям, �?о�?ма заг�?�?зки с под�?ве�?ждением п�?ав
- Рекоменда�?ии по изменени�? а�?�?и�?ек�?�?�?�? DotSound на основе анализа

## Ю�?иди�?еская го�?овнос�?�?

- �?азов�?й legal package в �?епози�?о�?ии
  - `LEGAL.md`
  - `docs/legal/archive/LEGAL_AUDIT_RU.md`
  - `docs/legal/USER_AGREEMENT.md`
  - `docs/legal/PRIVACY_POLICY.md`
  - `docs/legal/COPYRIGHT_POLICY.md`
  - `docs/legal/UPLOAD_RULES.md`
  - `docs/legal/LEGAL_TEXTS.md`
- Син�?�?онизи�?ова�?�? complaint/rightsholder flow во frontend и backend
  - `reason_type`, `rightsholder_name`, `proof_url` �?епе�?�? п�?о�?одя�?
  �?е�?ез schema -> route -> service -> repository -> UI
- �?бяза�?ел�?н�?й ак�?еп�? �?словий п�?и `UGC` upload
  - Checkbox в `UploadFileTab.tsx`
  - backend validation в `api/v1/tracks/user.py`
  - логи�?ование ве�?сии �?словий в `track_upload_meta`
- �?ос�?оянн�?е guardrails для аген�?ов и docs
  - `AGENTS.md`
  - `docs/ai-boundary-policy.md`
  - `.cursor/rules/legal-readiness.mdc`
  - `.claude/hooks` + `.claude/settings.json`:
  блок опасн�?�? shell-patterns, блок сек�?е�?ов, SessionStart кон�?екс�?
  - `.cursor/rules/shell-safety.mdc` + `.cursor/rules/session-start-context.mdc`
  для эквивален�?н�?�? guardrails в Cursor
- Явно �?азме�?ен current MVP external playback
  - �? `Track` добавлен�? `access_mode`, `source_platform`,
  `canonical_source_url`
  - `SoundCloud` import поме�?ае�? �?�?ек как
  `third_party_stream`
  - UI показ�?вае�? вне�?ний ис�?о�?ник и �?ежим дос�?�?па
- На �?�?овне модели �?азделен�? ка�?его�?ии �?�?еков
  - �? `Track` добавлен `catalog_type`
  - �?азовое �?азделение: `ugc`, `licensed`, `external_reference`
  - `SoundCloud` -> `external_reference`, `upload/telegram` -> `ugc`
- �?п�?бликова�?�? legal docs в самом п�?од�?к�?е как о�?дел�?н�?е дос�?�?пн�?е
с�?�?ани�?�?
  - `/legal` с�?ал hub-с�?�?ани�?ей
  - �?обавлен�? ма�?�?�?�?�?�? `/legal/terms`, `/legal/privacy`,
  `/legal/copyright`, `/legal/upload-rules`
  - Upload и complaint flow �?епе�?�? сс�?ла�?�?ся на конк�?е�?н�?е legal docs
- Раздели�?�? на �?�?овне модели/API `UGC`, `licensed` и
`external-source` �?�?еки, не полагаяс�? �?ол�?ко на �?екс�?ов�?е
дисклейме�?�?
- �?�?ове�?и�?�? current MVP с собс�?венн�?м playback пове�?�?
stream URL с�?о�?оннего се�?виса для �?ек�?�?его вне�?него ис�?о�?ника
(`SoundCloud`) и за�?икси�?ова�?�? residual risk
- Раздели�?�? об�?�?н�?�? пол�?зова�?ел�?ск�?�? жалоб�? и надлежа�?ее
�?ведомление п�?авооблада�?еля в о�?дел�?н�?е UX и workflow
- �?азово �?аздели�?�? об�?�?н�?�? жалоб�? и �?ведомление п�?авооблада�?еля
в UX
  - `ComplaintModal` подде�?живае�? �?ежим�? `user` и `rightsholder`
  - �?�?авооблада�?ел�?ский �?ежим �?�?еб�?е�? доп. поля и о�?дел�?н�?й �?екс�?
- Internal checklist для Terms вне�?ни�? ис�?о�?ников
  - `docs/legal/SOURCE_TERMS_CHECKLIST.md`
  - rule/docs п�?ивязан�? к п�?ове�?ке external-source integrations
- Сдела�?�? �?екс�?�? вне�?него импо�?�?а и поиска более �?ес�?н�?ми
  - `SearchView` явно поме�?ае�? SoundCloud как вне�?ний ис�?о�?ник
  - Текс�? п�?ед�?п�?еждае�?, �?�?о после добавления �?�?ек ид�?�? как вне�?ний
  по�?ок с�?о�?оннего се�?виса

## DevOps / CI

- **Branch coverage 95% (4 �?епо):** `scripts/check_branch_coverage.py` + `pytest --cov-branch` / `coverage.json` �?? по�?ог `percent_branches_covered` (см. Makefile / `AGENTS.md`). �?�?полнено: полн�?й п�?огон и п�?ове�?ка gate в Backend/PrivateCore/Bot/ComputeWorker.
- GitHub Actions: lint + test на PR (Backend, Bot, PrivateCore)
- Ав�?ома�?и�?еский деплой на VPS
- Рас�?и�?енн�?й healthcheck (`/api/v1/health/deep` �?? �?�?, Redis, S3)
- Health monitoring + alerting (uptime check, вне�?ний)

## Sprint 0..9 �?едизайна (2026-04, single-pass)

- Bot: like/dislike �?? добавлен Bearer + п�?авил�?н�?й internal id
- Frontend: `--progress` п�?об�?ас�?вае�?ся в `#pb-seek` (WebKit fix)
- Frontend: SW unregister �?ол�?ко в dev-�?ежиме
- Frontend: `env(safe-area-inset-bottom)` в `#nav`, `#player-bar`, `#main`
- PrivateCore: `is_within_grace_period` о�?секае�? б�?д�?�?ие `deleted_at`
- PrivateCore: `is_disposable_email` валиди�?�?е�? �?о�?ма�? email
- PrivateCore: �?ес�?�? для `account_deletion_policy` (15 кейсов)
- Backend: inline SQL в�?несен из `artists.py`, `admin/audio_compute.py`
- Backend: `dependencies.require_capability` испол�?з�?е�? �?епози�?о�?ий
- Backend: `transcoding._upload_hls` испол�?з�?е�? `asyncio.to_thread`
- Backend: `TrustedHostMiddleware` �?е�?ез `settings.allowed_hosts`
- Bot: throttling middleware подкл�?�?�?н к callback и inline_query
- Bot: вн�?�?�?енний HTTP-се�?ве�? binds `127.0.0.1` (�?е�?ез config)
- Bot: HTML escape во все�? �?о�?ма�?�?е�?а�? (`base`, `audio`, `inline`, `stats`)
- Bot: един�?й `mini_app_url` (�?б�?ан `backend_base_url` для WebApp)
- Bot: internal API возв�?а�?ае�? opaque error codes
- Bot: глобал�?н�?й `errors` handler с user-friendly fallback
- Bot: prefetched URLs испол�?з�?�?�?ся в `_edit_audio_batch` (gap-less)
- Bot: Dockerfile multi-stage с PrivateCore из �?оди�?ел�?ской ди�?ек�?о�?ии
- Frontend: дизайн-�?окен�? в `tokens.css` (8pt grid, motion, type scale)
- Frontend: `components.css` с Press, Sheet, Skeleton, EmptyState с�?илями
- Frontend: `Press`, `Sheet`, `EmptyState`, `SkeletonList`, `OfflineBanner`
- Frontend: �?ас�?и�?ен Icon-set (more-horizontal, queue, chevron-up/down)
- Frontend: Unicode замен�?н на `<Icon>` в FullscreenLyrics, PlaylistsView,
ComplaintModal, TrackCard, PlayerBar
- Frontend: `installTelegramThemeBridge`, `installViewportListener`,
`setBackButton`, `haptic`, `hapticNotification`
- Frontend: PlayerBar v2 �?? overflow menu + breakpoints + skeleton hit-area
- Frontend: TrackCard пе�?екл�?�?�?н на `usePlayerMeta` + `usePlayerActions`
- Frontend: CoverImage с `loading="lazy"` + `width/height`
- Frontend: aria-label/aria-pressed/aria-current на кл�?�?ев�?�? кон�?�?ола�?
- Frontend: `useConfirm` пе�?еписан с п�?авил�?н�?м unmount cleanup
- Frontend: index.html splash сок�?а�?�?н с 1800ms до 1200ms safety cap
- PrivateCore: README ак�?�?ализи�?ован, ве�?сия `0.2.0`, policy с
bounded-transport exception
- Backend: `/api/v1/health/deep` (DB / Redis / S3 ping)
- Backend: `X-Request-ID` о�?да�?�?ся в заголовке о�?ве�?а
- Docs: `docs/design-system.md`, `docs/redesign-rationale.md`

---

*�?оследнее обновление: 2026-04-24 (multi-platform streaming: YouTube + Bandcamp).*

## Session Updates (2026-05-06)

- [x] Admin dashboard UI refresh: interactive online history chart with range switch (15m/1h/6h/24h), trend badge, and additional RPS/latency cards in `frontend/src/admin/routes/DashboardRoute.tsx` + `frontend/src/admin/styles/admin.css`.
- [x] Mini App loading-screen stabilization: unified startup lifecycle between `frontend/index.html` and `frontend/src/App.tsx`, removed polling race, and smoothed splash animation in `frontend/src/styles/global.css` (including reduced-motion profile).
- [x] Frontend-wide animation stabilization pass: unified motion tokens/easing in `frontend/src/styles/tokens.css`, softened keyframes and interaction feedback in `frontend/src/styles/animations.css` and `frontend/src/styles/components.css`, plus stronger reduced-motion guards for looping effects.
- [x] Focused motion polish for core UX zones: smoother interactions/transitions in `frontend/src/components/PlayerBar/PlayerBar.tsx` and `frontend/src/styles/global.css` for PlayerBar, TrackCardSheet, and Home cards/carousels (reduced jitter, calmer active states, better reduced-motion fallback).
- [x] Admin UI pass for secondary routes: KPI cards + sparklines for Users/Tracks/Complaints, plus live-toggle and loading/empty chart states for Metrics and Dashboard.
- [x] Admin dashboard statistics: backend `/api/v1/admin/dashboard/stats` with period aggregations (today/7d/30d), plus frontend stats block with KPI cards and top tracks list.
- [x] Admin tabs analytics expansion: track analytics (popular tracks + uploads timeline) and admin activity analytics (actions timeline + top admins) with period filters in `Tracks` and `Users` routes.

## �?ла�?�?о�?м�? �?? б�?д�?�?ее

- **�?иб�?идн�?й плее�?**: для пла�?�?о�?м с о�?и�?иал�?н�?ми embed-видже�?ами �?еализова�?�?
`access_mode="official_embed"` �?? �?�?ани�?�? embed URL, о�?�?исов�?ва�?�? `<iframe>` вмес�?о
на�?ивного плее�?а, о�?кл�?�?и�?�? EQ. �?�?ио�?и�?е�?: YouTube (�?�?еб�?е�? TOS �?аздел 5.D).
- **VK �?�?з�?ка**: OAuth �?же �?еализован (`linked_accounts`, scope `audio`). Н�?жно добави�?�?
`VKStreamService` (пол�?�?ае�? HLS-URL �?е�?ез `audio.getById` с user OAuth token) и �?ас�?и�?и�?�?
`playback.py`. �?�?ложено �?? �?оссийский се�?вис.
- **Яндекс �?�?з�?ка**: н�?жен нов�?й OAuth-п�?овайде�? (`Yandex OAuth`, oauth.yandex.ru) +
нео�?и�?иал�?н�?й API-адап�?е�?. �?�?ложено �?? �?оссийский се�?вис.
- **YouTube TOS compliance**: согласно TOS YouTube �?аздел 5.D п�?ямой API-с�?�?иминг зап�?е�?�?н.
�?олгос�?о�?но: миг�?и�?ова�?�? на `access_mode="official_embed"` (iframe-embed), API-с�?�?иминг
ос�?ави�?�? �?ол�?ко как dev/fallback.

## Sprint concurrency hardening (2026-04-22)

- Backend: миг�?а�?ия `0045_dedupe_unique_constraints` �?? partial UNIQUE
на `tracks.sc_url WHERE sc_url IS NOT NULL` и на
`(imported_from, external_id) WHERE external_id IS NOT NULL`,
`Index` об�?явлен�? в `app/models/track.py:Track.__table_args`__
(созда�?�?ся и для �?ес�?овой SQLite-с�?ем�?)
- Backend: `scripts/dedupe_tracks.py` �?? pre-migration helper, dry-run
по �?мол�?ани�?, ме�?джи�? д�?бли по `sc_url` и `(imported_from, external_id)`
с union-find и FK-redirect для likes/dislikes/playlists/track_artists/
track_lyrics/track_info/track_upload_meta/complaints/listen_events/
comments/lyrics_jobs/search_events/messages
- Backend: `SoundCloudService.import_or_get_track` пе�?еписан на
`INSERT ... ON CONFLICT (sc_url) WHERE sc_url IS NOT NULL DO NOTHING RETURNING` + fallback `SELECT`; `external_import_worker` об�?�?н�?�? в
`try/except IntegrityError` на сл�?�?ай rolldown-с�?ена�?ия
- Backend: миг�?а�?ия `0046_add_lyrics_sync_source_name` �??
`track_lyrics.sync_source_name VARCHAR(50) NULL`, п�?об�?ос �?е�?ез
`LyricsRepository.create_or_update`, `LyricsResponse` schema,
`_result_to_payload(getattr(gen_result, "sync_source_name", None))`
- Backend: `app/services/sc_semaphore.py` �?? Redis-based counting
semaphore (sorted-set + Lua acquire) вок�?�?г SoundCloud `search`/
`resolve_url`/`get_stream_info`, env `SOUNDCLOUD_GLOBAL_CONCURRENCY=4`
- Backend: per-track Redis lock в `lyrics_worker.generate_lyrics_task`
(�?е�?ак�?о�?инг �?е�?ез outer wrapper + `_generate_lyrics_task_impl`),
env `LYRICS_PER_TRACK_LOCK_TTL_SECONDS=300`; race-protected
�?е�?ез `SET NX EX` + Lua-release-on-match
- Backend: `app/services/import_queue_dispatcher.py` �?? backpressure
�?е�?ез с�?а�?�?с `"queued"`, env `IMPORT_MAX_CONCURRENT_JOBS=10`,
`IMPORT_PER_USER_MAX_CONCURRENT=2`, dispatcher loop зап�?скае�?ся
в WORKER_STARTUP. `ImportService.start_import` возв�?а�?ае�? job
с `status="queued"` если глобал�?н�?й или per-user cap заня�?;
`get_queue_position` для UI; `cancel_job` и `_get_active_job`
понима�?�? `"queued"`
- Backend: `app/services/lyrics_global_orchestrator.py` �??
един�?й pacer �?е�?ез `BLPOP lyrics:queue:default`, �?и�?е�?лаг
`LYRICS_GLOBAL_ORCHESTRATOR_ENABLED=true`, заменяе�? per-job
пейсинг в `import_lyrics_worker.process_import_lyrics_task`
(legacy mode со�?�?ан�?н, ак�?иви�?�?е�?ся в�?кл�?�?ением �?лага). Global
circuit-breaker на 5 под�?яд `captcha|pool_exhaust|exhausted`
сигналов из proxy_pool
- Backend: API `GET /import/{id}/status` и `/import/active`
возв�?а�?а�?�? `queue_position` для queued джобов
- Backend: `main.py` за�?егис�?�?и�?овал во�?ке�?�?
`app.services.import_queue_dispatcher` и
`app.services.lyrics_global_orchestrator`
- Frontend: `ImportView.tsx` �?? новая �?аза `"queued"` с
о�?об�?ажением `queue_position`, polling пе�?екл�?�?ае�?ся межд�?
`queued <-> importing` без пе�?есоздания ин�?е�?вала
- Frontend: `LyricsPanel.tsx` и `FullscreenLyrics.tsx` �?? admin-only
debug-блок «�?с�?о�?ник �?екс�?а» / «Син�?�?онизовал» в самом кон�?е
о�?об�?аж�?нного �?екс�?а, гей�?и�?ся �?е�?ез `getIsAdmin()`; CSS
`.lyrics-debug-attribution` (минимализм, моно�?�?ом, monospace)
- Docs: `docs/private-core-dependency-policy.md` пополнен �?абли�?ей
оп�?ионал�?н�?�? полей `GenerateResult` (вкл�?�?ая нов�?й
`sync_source_name` �?? PrivateCore-side �?�?еб�?е�?ся добави�?�? поле,
Backend �?же forward-compatible �?е�?ез `getattr`)
- Tests: `test_soundcloud_service::test_import_or_get_track_dedup_via_unique_index`,
`test_lyrics_worker::test_sync_source_name_propagates_to_repo`,
`test_lyrics_global_orchestrator.py` (нов�?й �?айл, 7 �?ес�?ов на
serialize/deserialize/process_one), `test_import_service` (3 нов�?�?
�?ес�?а на backpressure + queue_position + cancel queued),
`test_import_lyrics_worker` autouse-�?икс�?�?�?а �?о�?си�? legacy �?ежим

## Sprint multi-importer library (2026-04-22)

- Backend: миг�?а�?ия `0047_add_user_track_library` �?? many-to-many
�?абли�?а `user_track_library (user_id, track_id, source, imported_at)` с composite PK + индекс `(user_id, imported_at)`.
Backfill из `tracks.uploaded_by_id` �?�?об�? с�?�?ес�?в�?�?�?ие �?�?еки
попали в библио�?ек�? владел�?�?а
- Backend: `app/models/user_track_library.py` (модел�?) +
`app/repositories/user_track_library.py` (`add` идемпо�?ен�?ен
�?е�?ез `INSERT ... ON CONFLICT DO NOTHING`, `list_by_user`,
`count_by_user`, `has`, `remove`)
- Backend: auto-link во все�? flow создания �?�?ека �??
`external_import_worker.py` (после `import_or_get_track`,
вкл�?�?ая dedup-resolved сл�?�?ай), `import_worker.py` (telegram),
`upload_service.py` (UGC). �?демпо�?ен�?но �?? пов�?о�?н�?й импо�?�?
одной песни одним �?зе�?ом не д�?бли�?�?е�?
- Backend: `GET /api/v1/users/me/library` �?? paginated, ORDER BY
`imported_at DESC`, `playable_only` filter; `TrackService.list_library`,
`UserTrackLibraryRepository.list_by_user` с JOIN
- Backend: `LyricsService._get_editable_track` �?? для
`catalog_type='external_reference'` �?едак�?и�?ование ли�?ики �?ол�?ко
админом, для UGC о�?игинал�?н�?й uploader (как �?ан�?�?е). �?се ме�?од�?
`create_or_update`/`update_sync`/`delete_lyrics`/`redefine`/
`trigger_auto_generation`/`cancel_auto_generation` пе�?еведен�?
на нов�?�? п�?ове�?к�?
- Backend: defensive `LyricsRepository.get_by_track_id` skip в
`lyrics_global_orchestrator._process_one` �?? зак�?�?вае�? race
window межд�? `_enqueue_to_global_queue` и момен�?ом об�?або�?ки
(д�?�?гой во�?ке�? мог �?же со�?�?ани�?�? ли�?ик�?)
- Frontend: `api.getMyLibrary(page, size, playableOnly)` ме�?од;
`ProfileView` пе�?екл�?�?�?н с `getMyTracks` на `getMyLibrary`,
пол�?зова�?ел�? види�? и свои аплоад�?, и импо�?�?и�?ованн�?е �?�?еки
- Frontend: `LyricsPanel` п�?инимае�? `catalogType` prop, кнопки
�?едак�?и�?ования гей�?я�?ся �?е�?ез `canEdit = isExternalRef ? isAdmin : isOwner`. �?се 4 �?о�?ки ownership-gating обновлен�?.
`TrackCardSheet` п�?об�?ас�?вае�? `catalog_type`, edit-pane lyrics-toggle
кнопка ск�?�?�?а для non-admin на external_reference
- Frontend: `ImportView` �?аза `done` показ�?вае�? «Т�?еки добавлен�?
в ва�?�? библио�?ек�? (п�?о�?ил�?)»
- Tests: `test_user_track_library.py` (7 кейсов: idempotency,
shared-by-two-users, ordering, remove, count, has),
`test_external_import_worker::test_two_users_share_track_with_two_library_links`,
`test_lyrics_service` (3 нов�?�?: external blocks owner, allows admin,
ugc owner ok), `test_lyrics_global_orchestrator::test_process_one_skips_when_lyrics_already_in_db`

## Sprint admin / auth (2026-04-19)

- Frontend: син�?�?онн�?й `api.restoreSession()` в `main.tsx` �?�? �?енде�?а �?? �?би�?ае�? �?анн�?�? гонк�? �?окена с AdminProvider/PlayerProvider
- Frontend: `AdminContext.tsx` гей�?и�? `getAdminManifest()` на нали�?ие �?окена и подписан на `app-auth-ready` + `i18n.languageChanged`; �?б�?ан orphan-импо�?�? `adminBundleUrl`
- Frontend: `App.init()` п�?оп�?скае�? `api.authTelegram('')` п�?и п�?с�?ом initData (�?би�?ае�? 422 + 500ms �?е�?�?ай в ngrok-�?ежиме)
- Frontend: `connectWS(...)` в�?з�?вае�?ся с�?аз�? в `verifyTelegramCode` / `verifyMagicLink` / `verify2FA`, пл�?с диспа�?�? `app-auth-ready`
- Frontend: `restoreSession()` восс�?анавливае�? `auth-user-id` из JWT `sub`, если он по�?е�?ян �?? �?би�?ае�? «п�?и обновлении п�?оси�? код»
- Frontend: Suspense fallback с timeout-ом и retry в `App.tsx` (`RouteFallback`) �?? �?би�?ае�? «�?�?�?н�?й эк�?ан» п�?и завис�?и�? lazy-�?анка�?
- Frontend: i18n RU/EN для всей админки (`admin.`* namespace в локаля�?, `useTranslation` в `AdminApp`, `AdminShell`, все�? auth-�?о�?ма�? и routes)
- Frontend: `AuthGate` зап�?скае�? `ensureCsrf` и `bootstrapMetadata` па�?аллел�?но �?е�?ез `Promise.allSettled` и п�?�?ае�?ся `adminApi.refresh()` на с�?а�?�?е �?? admin-сессия пе�?еживае�? reload без TOTP
- Frontend: `useAdminAuth.capabilities` наполняе�?ся из мани�?ес�?а после �?спе�?ного refresh �?? `useCapability` �?епе�?�? �?або�?ае�?
- Frontend: proactive refresh за 30 сек до expiry в `adminFetch`; п�?и �?ейле refresh с�?а�?�?с `'needs_login'` вмес�?о `'unauth'`
- Frontend: `AdminShell` �?? �?ас�? в�?несен�? в изоли�?ованн�?й `<Clock />`, ос�?ал�?ная панел�? не пе�?е�?исов�?вае�?ся кажд�?�? сек�?нд�?
- Frontend: refetchInterval подня�? до 15-30 сек и `refetchIntervalInBackground: false` во все�? админ-routes (Dashboard, Logs, Tasks, Metrics, Containers, Security, Settings, AudioCompute)
- Frontend: �?дал�?н orphan-�?айл `frontend/src/admin/AdminDashboardView.tsx`
- Frontend: `?nosw=1` в URL �?аз�?егис�?�?и�?�?е�? service worker (о�?ладка на ngrok)
- Frontend: �?б�?ан д�?бли�?�?�?�?ий `<Route path="/admin">` без `*` в `App.tsx` �?? nested `<Routes>` в `AdminApp` �?епе�?�? ко�?�?ек�?но �?енде�?и�? `DashboardRoute`
- Frontend: `adminApi.refresh()` и `adminApi.logout()` бол�?�?е не �?л�?�? `body: {}` �?? backend �?епе�?�? �?и�?ае�? refresh token из httpOnly-cookie без 422 о�? валида�?ии `AdminRefreshRequest`

## Sprint bugfix (2026-04-20)

- **(0)** Policy amendment: �?ас�?и�?и�?�? "Source Attribution Exception" на lyrics / track-info п�?овайде�?ов (`CLAUDE.md` + `docs/ai-boundary-policy.md`)
- **(1)** Track info: пе�?енос из вне�?ней кнопки вн�?�?�?�? `TrackCardSheet` (после блока «по�?ожие �?�?еки»), DEBUG-refresh (admin), ав�?озаг�?�?зка и polling
- **(2)** Track info worker: `/api/v1/tracks/{id}/info` зависае�? в `fetching` �?? stale-retry в се�?висе, `asyncio.wait_for` timeout 90s в во�?ке�?е, `fetched_at` о�?�?ажае�? последнее сос�?ояние
- **(3)** `TrackCardSheet`: белая заливка п�?ог�?есс-ба�?а �?? CSS gradient с `--progress` + inline style на seek-input
- **(4)** `SettingsSheet`: кнопка «Назад» с label + Telegram BackButton + Esc
- **(5)** `TrackCardSheet`: к�?ес�?ик 44�?44, safe-area-inset-top/right, не в�?�?оди�? за �?амки
- **(6)** `TrackCardSheet`: «�?е�?ей�?и к ав�?о�?�?» испол�?з�?е�? `track.artist` �?е�?ез `onOpenArtist`; �?яд заг�?�?з�?ика пе�?еименован
- **(7)** Admin: `/logs/query` и `/metrics/range` возв�?а�?а�?�? `source_status` + `/system/observability` endpoint, banner в `LogsRoute` / `MetricsRoute`
- **(8)** Admin lyrics-jobs: индивид�?ал�?н�?й cancel (inline-кнопка) + bulk `POST /tasks/lyrics-jobs/cancel-queued`; `queued` с�?аз�? пе�?еводи�?ся в `cancelled` в �?�?
- **(9)** Admin Artists: `DELETE /artists/{id}`, клик по имени �?? `/mini_app/artist/:id` (новая вкладка), fix да�?�? �?е�?ез fallback на `created_at`, `updated_at` добавлен в `ArtistResponse`
- **(10)** Admin Tracks: existing `DELETE` + visibility-toggle + inline `<audio>` + о�?к�?�?�?ие `/mini_app/track/:id`
- **(11)** Admin Users: ban/unban + `POST /users-ext/{id}/force-logout` (revoke admin sessions + Redis marker) + `POST /users-ext/{id}/message` (DM �?е�?ез `ChatService`/`MessageService`)
- **(12)** Lyrics: cache-hit с text-only п�?и `with_sync=true` п�?е-со�?�?аняе�? �?екс�? в �?�? и п�?одолжае�? в audio-based sync flow
- **(13)** WS: `_is_ws_open()` guard + `try/except (WebSocketDisconnect, RuntimeError)` �?? �?анний в�?�?од из `_broadcast_loop`
- **(14)** Lyrics: `LyricsResponse.source_name` (optional) для UI-attribution + `lyrics_provider_name` / `track_info_provider_name` env-flag selectors; алго�?и�?мика ос�?а�?�?ся в PrivateCore

## Playback variants / composition grouping (2026-04-29)

- `[x]` PrivateCore: `playback_variant_policy` (по�?ядок пла�?�?о�?м, tolerance)
- `[x]` Backend: `composition_group_id`, `PlaybackVariantService`,
  `build_track_response` / `dedupe_and_build_track_list`,
  `TrackResponse.playback_variants`, лайки/дизлайки по г�?�?ппе,
  коммен�?а�?ии по `variant_ids`, read-only stream fallback
- `[x]` Frontend: �?ип�? API, `LikesContext` по
  `playback_variant_track_ids`, пе�?екл�?�?а�?ел�? ис�?о�?ника в �?и�?е
- `[x]` Tests: mock `catalog_only_lyrics_task.kiq` в
  `create_test_track` / `mock_taskiq` и в `test_upload_track_success`
- `[x]` `scripts/backfill_composition_groups.py` (stub)

## Home Menu Redesign �?? v2 (2026-05-04)

- `[x]` **ArtistFollowRepository**: `list_followed_artists(user_id, limit)` �?? `list[Artist]`
- `[x]` **Schemas**: `FollowedArtistItem`, `FollowedArtistListResponse` в `artist_follow.py`
- `[x]` **API**: `GET /api/v1/artists/followed` endpoint
- `[x]` **PrivateCore**: `build_genre_mixes()`, `GenreMixResult`, `MAX_GENRE_MIXES`, `GENRE_MIX_SIZE`
  в `recommendation_engine.py`; экспо�?�?�? в `services/__init__.py`
- `[x]` **Backend**: `GET /api/v1/recommendations/genre-mixes` (endpoint + `RecommendationService.get_genre_mixes()`)
- `[x]` **Backend**: `GET /api/v1/recommendations/radio` �?? добавлен `exclude_ids` query param (max 30)
- `[x]` **RecommendationService.get_radio**: п�?инимае�? `exclude_ids: list[int] | None`
- `[x]` **Schemas**: `GenreMixItemResponse`, `GenreMixesResponse` в `recommendation.py`
- `[x]` **global.css**: все Home v2 CSS-класс�? (greeting, quick-grid, carousel, artist-strip, genre-mix-card,
  player-radio-badge, top nav-indicator)
- `[x]` **api.ts**: `getFollowedArtistsList()`, `getGenreMixes()`, обновл�?н `getRadio(excludeIds?)`
- `[x]` **types/api.ts**: `FollowedArtistItem`, `GenreMixItem`, `GenreMixesResponse`
- `[x]` **HomeView.tsx**: полн�?й �?едизайн �?? п�?иве�?с�?вие, quick-grid, genre mixes carousel,
  followed artists strip, сек�?ионн�?е ка�?�?сели �?�?еков по section_type
- `[x]` **BottomNav.tsx**: ве�?�?ний индика�?о�? (`.nav-btn__indicator`) для ак�?ивного �?аба
- `[x]` **GenreMixView.tsx**: нов�?й view `/genre-mix/:genre`
- `[x]` **App.tsx**: ма�?�?�?�?�? `/genre-mix/:genre`; lazy-import `GenreMixView`
- `[x]` **Icon.tsx**: добавлен�? иконки `radio`, `users-following`
- `[x]` **PlayerContext.tsx**: `radioMode`, `radioSeedTrackId`, `startRadio()`, `stopRadio()`;
  `playNext()` �?? ав�?о-fetch п�?и п�?с�?ой о�?е�?еди в radio-�?ежиме; `played_ids Set` (max 50)
- `[x]` **RadioView.tsx**: пе�?е�?або�?ан �?? кнопка «�?ап�?с�?и�?�? бесконе�?ное �?адио», индика�?о�? �?ежима,
  ис�?о�?ия п�?осл�?�?ивания
- `[x]` **PlayerBar.tsx**: `.player-radio-badge` п�?и ак�?ивном `radioMode`; клик �?? `/radio`
## Chats / Track Share (2026-05-04)

- [x] Share track to chat ? modal picker in TrackCardSheet, send via api.sendMessage(..., { type: 'track_share', shared_track_id }), and shared-track bubble with Play in ChatBubble.

- [x] Chat share: albums and playlists (shared_album_id, shared_playlist_id) + updated Home track/artist card styling for .sound consistency (2026-05-04).

## Lyrics Roadmap

- [x] Add support for per-track lyrics translations (store translated text separately from original lyrics), including backend API/model + minimal language switch in lyrics UI (2026-05-06).

- [x] RU/EN brand switch for mini app: default '.\\u0437\\u0432\\u0443\\u043a', English '.sound' (loader, splash, auth, home, admin shell, static build sync) �?? 2026-05-04

---

## Future Features & Enhancements (Planned May 2026)

- [ ] **AI-Mood & Genre Tagging (v1)**
    - [ ] Ав�?ома�?и�?еское �?еги�?ование на основе анализа а�?дио (ComputeWorker).
    - [ ] Анализ ме�?аданн�?�? и �?екс�?а песен �?е�?ез LLM (оп�?еделение нас�?�?оения/жан�?а).
    - [ ] Х�?анение в Backend и о�?об�?ажение в UI.
- [ ] **Listening Party (v2)**
    - [ ] �?н�?ег�?а�?ия с �?а�?ами (создание комна�? вн�?�?�?и г�?�?пп).
    - [ ] "�?емок�?а�?и�?ная о�?е�?ед�?" (голосование за �?�?еки).
    - [ ] Ул�?�?�?ение UI и син�?�?ониза�?ии.
- [ ] **�?�?з�?кал�?н�?е п�?о�?или и с�?а�?ис�?ика**
    - [ ] �?а�?�?о�?ки "Топ а�?�?ис�?ов/�?�?еков" меся�?а для �?е�?инга.
    - [ ] �?е�?ал�?ная с�?а�?ис�?ика в п�?о�?иле (�?ас�? п�?осл�?�?ивания, л�?бим�?е жан�?�?).
    - [ ] Сек�?ия "�?а�? �?оп" на главной.
- [ ] **�?инами�?еские плейлис�?�?**
    - [x] "Weekly Top 50" -- 2026-05-06: PrivateCore weekly_top_policy (rank_weekly_top_tracks, blend log(listens_7d)+log(likes_7d), WEEKLY_TOP_SCORE_VERSION); Backend RecommendationRepository.get_qualified_listens_7d_counts, RecommendationService.get_weekly_top_playlist with Redis cache (TTL 30 min), GET /api/v1/recommendations/weekly-top; Frontend WeeklyTopView (/weekly-top), api.getWeeklyTopPlaylist, WeeklyTopPlaylistResponse type, flame icon, Home quick-grid card.
    - [ ] "�?аб�?�?�?е сок�?ови�?а" (лайкн�?�?ое давно).
- [ ] **PWA Offline Mode (v2) [High Priority]**
    - [ ] �?э�?и�?ование HLS �?анков в Service Worker.
    - [ ] Надежн�?й UI для о�?лайн-�?ежима.
- [ ] **Anti-Abuse Fingerprinting**
    - [ ] �?е�?енос логики в PrivateCore.
    - [ ] Анализ поведения для бо�?�?б�? с нак�?�?�?ками.


- [x] Public UI: admin inline editing for playlists/albums/tracks via non-admin routes with backend admin checks + reorder endpoints (2026-05-05).

- [x] Frontend: fixed share copy toast layering above share modal for track/album/playlist (z-index via --z-toast, 2026-05-05).

- [x] Frontend: TrackCardSheet now resolves album edit/share via fallback track.album_id (for mixes/playlists where card.album may be empty), 2026-05-05.

- [x] Frontend: share copy toasts can render at top (position=top) to avoid overlap with share modal; admin flag fallback from JWT claim is_admin in getIsAdmin, 2026-05-05.

- [x] Frontend: Apple-like .зв�?к splash typography + loading animation; edit UI gates in TrackCardSheet simplified to admin/debug/dev for mix album editing on Home, 2026-05-05.
- [x] Frontend: ArtistView now shows a prominent monthly unique listeners KPI card in artist header (always visible with API fallback), 2026-05-05.
- [x] Frontend: ArtistView monthly listeners moved to compact inline text under artist avatar/name with new `users-listeners` SVG icon, 2026-05-05.
- [x] Frontend: Home greeting now shows only day/evening format (`�?об�?�?й ден�?|ве�?е�?`) with optional user name (`| {{name}}`) and fallback without name, 2026-05-05.
- [x] Frontend: Home featured card now has a clearer right-side `Play` pill button near the upper-right area for explicit playback affordance, 2026-05-05.

- [x] Backend+Frontend: server-side genre-mix overrides (DB table + API PUT /recommendations/genre-mixes/{genre}) and hybrid track search in album/playlist/mix editors; removed local-only mix persistence, 2026-05-05.

- [x] Admin+Public artists: added batch AI prompt/import for artist supplemental text, switched artist card priority to Platform supplemental content, and temporarily commented out Yandex tab/UI in ArtistView, 2026-05-05.

- [x] Genre mix page now loads by exact endpoint GET /api/v1/recommendations/genre-mixes/{genre} (with override fallback), fixing lost edits after reload on /mini_app/genre-mix/:genre, 2026-05-05.

- [x] Frontend: fixed Profile settings feedback test in Telegram Android by hardening haptic fallback (WebApp + navigator.vibrate) and increasing audible UI test sound baseline, 2026-05-05.

- [x] Frontend: wired haptic+tap sound to regular Profile/Settings UI actions (tabs, profile actions, edit/save/cancel, toggles), not only feedback test buttons, 2026-05-05.

- [x] Frontend: improved Telegram Android haptic reliability (`selectionChanged` -> `impactOccurred` fallback + throttled `hapticTick`) and added micro-vibration ticks for EQ/track-volume sliders; regenerated deeper, neutral UI feedback sounds, 2026-05-05.

- [x] Admin compute: lyrics + generic compute job queue priority and worker pin, in-flight reassignment (lease release), API + Audio Compute UI; ComputeWorker treats 404 on result/fail as abandoned job (2026-05-05).

- [x] Frontend UI stability pass: removed nested interactive cards in `HomeView` (no `button` inside `button`), throttled carousel arrow scroll updates via `requestAnimationFrame`, added TrackCardSheet stale-request guard for fast track switching, and included safe-area bottom inset in `.tcs-sheet` padding (2026-05-06).

- [x] Mini App: fixed artist navigation regressions (followed artist opens artist card, tabs close active artist/author overlay) and upgraded Artist `Similar` section to photo cards with horizontal slider + arrow controls (2026-05-06).

- [x] Activation improvements (phase 2, 2026-05-06): backend persists onboarding activation timestamps (`auth_first_seen_at`, `first_play_at`), computes server-side `ms_from_auth_server`, and aggregates activation events in Redis for funnel metrics.
- [x] Admin dashboard (2026-05-06): added activation funnel endpoint `/api/v1/admin/dashboard/activation-funnel` and KPI cards for auth->first-play time, onboarding completion rate, skip rate, and first-session plays.
- [x] Onboarding UX (2026-05-06): resumable draft state in localStorage, feature-flag-aware smart skip (`feature.onboarding.smart_skip_enabled`), neutral calibration "skip" option, and import-progress CTA to listen to already imported tracks immediately.

- [x] Recsys: catalog station + album co-artist overlap weights in PrivateCore (`similarity_signal_policy`), `UserPrefs.similar_artist_weights`, hybrid `/artists/{id}/similar`, station-neighbor pool for `/recommendations/similar/{track_id}` (2026-05-07).

## Mini App iOS-redesign / поток 2 (прогресс)

- [~] **Stage D (library): поиск, медиатека, лайки, плейлисты** — 2026-05-07: `redesign-library.css`, `SearchView` (чипы фильтра сущностей, motion), `LibraryView` (tabs + layoutId, daily mix `MotionPress`), `LikedView` (сортировка, чипы `MotionPress`, sticky-шапка), `PlaylistsView` (сетка, `LongPressMenu`, поток «поделиться» с экрана списка), ключи `redesign.library.*` в `i18n_extra2_*.json`. Дальше: polish профиль/настройки, Stage F (artist shell), Stage H (recap), отдельные коммиты после `tsc`/`build`.
