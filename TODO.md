# DotSound - TODO Tracker

> Этот файл поддерживается автоматически ИИ-агентом.
> Агент обязан: (1) прочитать этот файл в начале сессии,
> (2) обновить статус после выполнения задач,
> (3) добавить новые задачи если они возникли.

## Статус

- `[ ]` - не начато
- `[~]` - в процессе
- `[x]` - завершено
- `[-]` - отменено / неактуально

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

- [x] **Профиль: дизлайки в блоке действий + адаптив (2026-05-08)** — убран четвёртый таб
  сверху; «Дизлайки» в `ProfileActions` после «Понравившееся»; подшапка «К профилю» +
  заголовок; вкладка «Профиль» активна и для подэкрана дизлайков; сетка действий 3–4
  колонки от 640/960px; блок «Ваше прослушивание» в карточке (`ListenerStats` + CSS).
- [x] **Добавление треков в плейлист (2026-05-08)** — `PlaylistsView`: пустое поле — первая
  страница каталога (12 playable) и «Ещё из каталога»; текстовый запрос **от 2 символов**
  — поиск по каталогу с той же пагинацией; **1 символ** — только фильтр медиатеки;
  медиатека показывается чанками по 12 + «Ещё из медиатеки». Одно нажатие добавляет трек,
  острова успех/ошибка; `PlayerBar` → `AddToPlaylistSheet`; `api.getPlaylists(page,size)`.

- [x] **Обложки пользовательских плейлистов (2026-05-07)** — загрузка/смена
  собственной обложки (POST/DELETE `/api/v1/playlists/{id}/cover`), флаги
  `cover_auto_suppressed` + `collage_generated_at`, одноразовый коллаж из
  обложек треков при ≥4 видимых треках (PrivateCore `playlist_cover_policy`),
  Mini App (`PlaylistsView`) и `cover_proxy` для префикса `playlist-covers/`.

- [x] **Admin + lyrics pipeline: жанр и настроение по тексту** —
  эвристика в PrivateCore (`text_genre_mood_infer`), автоприсвоение
  после `LyricsRepository.create_or_update`, batch prompt/import в
  админ-чеке и `LYRICS_DERIVED_GENRE_MOOD_ENABLED` в `.env.example`.
- [x] **View Transitions + React** — `flushSync` в колбэке
  `startViewTransition` в `App.tsx` (иначе снимок «нового» кадра до коммита
  React — пустой/чёрный экран при смене вкладок/маршрутов).
- [x] **Глобальный UI redesign `.sound`** — обновлены splash/loading,
  иконки PWA, домашний экран, поиск, лайки, профиль, admin shell и
  Telegram bot copy/keyboards без изменения backend API, PrivateCore и
  ComputeWorker.
- [x] **iOS 2026 global redesign — Stage G (Admin) + Stage I (Upload/Import) + Phase 3 polish**
  — AdminRangeSwitch, DataTable sticky-glass + MotionPress sort, StatusPill icons;
  DashboardRoute/TasksRoute/SchedulesRoute/TracksRoute/UsersRoute/ArtistsRoute/ContainersRoute
  migrated to MotionPress + AdminRangeSwitch + showIsland toasts; UploadFileTab split into
  wizard steps (UploadStepAudio/Details/Cover/Preview + UploadComboBox); URL import tabs
  unified via UrlImportTab; ImportActivityBanner → headless DynamicIsland driver;
  toast.* → showIsland migration across HomeView/TrackCard/TrackCardSheet/TrackList/ArtistView;
  PlayerBar overflow-menu → MotionPress; QueueSheet/NowPlayingView/SearchView/LegalView/
  FullscreenLyrics bare buttons → MotionPress; dead .import-activity-banner CSS removed;
  i18n keys added for all hardcoded RU strings.
- [x] **Search + Artist route regressions (2026-05-07)** — `SearchView`: параллельная
  загрузка `getDiscover` + `getFeaturedPlaylists`, секция редакционных плейлистов,
  исправлен пустой hint при непустом discover, навигация на `/playlist/:id` из строк
  поиска, `tabHasResults` и пустой стейт вкладки «Плейлисты». `ArtistView` (route):
  каталог релизов + дискография + `ArtistCatalogReleasePanel`, Telegram back для
  подэкрана релиза; legacy `components/ArtistView/ArtistView.tsx` переименован в
  `ArtistProfileStandalone` (не использовался в маршрутах).
- [x] **Mini App responsive touch (2026-05-07)** — breakpoint ~560px: `MotionPress`
  icon 36px на desktop fine-pointer / 44px на touch; PlayerBar элементы управления и
  меню под `--tap`; на узкой ширине лайк и «назад» в overflow; главная —
  4 top quick-tile (`MIX_SHORTCUT_TILES` + `homeShortcuts.ts`), остальные миксы/радио
  в `ProfileActions`; hero колонкой на телефоне; `TrackCard` owner кнопки через
  `MotionPress`, дубль visibility скрыт на узком экране; чат — back/bubble coarse;
  **итоги года** — пункт профиля и `/recap` только в декабре (`recapSeason.ts`),
  иначе stub.
- [x] **Desktop: отдельные клики артист / трек (2026-05-07)** — при
  `(min-width: 561px) and (pointer: fine)`: строка исполнителя ведёт на карточку
  артиста через `resolveArtistByName`, клик по названию трека/обложке — как
  раньше (воспроизведение в списках, карточка в плеере / Now Playing).
  Компоненты: `TrackCard`, `PlayerBar`, `QueueSheet`/`QueueRow`, `NowPlayingView`,
  главная (`HomeTrackTile`, hero-artist), `ChatBubble`; хуки
  `useDesktopFinePointer`, `useNavigateToArtistByName`.
- [x] **Редактирование аватарки профиля (2026-05-07)** — в режиме редактирования
  `ProfileView`/`ProfileHero`: выбор JPEG/PNG/WebP до 2 МБ, превью через blob,
  загрузка `POST /api/v1/users/me/avatar` при «Сохранить» (API уже было);
  отмена сбрасывает черновик фото и имя до baseline; острова ошибок через
  `showIsland`; ключи в `i18n_extra2_ru/en.json`.
- [x] **Медиатека: история прослушиваний — дата и длительность** (2026-05-07) —
  `GET /users/me/listen-history` добавляет в `TrackResponse` поля
  `last_listen_at` и `last_listen_seconds` (учёт вариантов воспроизведения);
  `HistoryList` и `TrackCardSheet` показывают дату/время и «прослушано mm:ss`;
  i18n `redesign.library.*`, `trackSheet.lastListen*`.
- [x] **Плейлисты: добавление только воспроизводимых треков** (2026-05-07) —
  `playlist_track_eligibility` + проверка при `POST /playlists/.../tracks` и админ-добавлении;
  поиск/`me/library` с `playable`, UI выбора в `PlaylistsView`, админ-пикер по
  владельцу (`for_playlist_owner_id`, `playable_only`), i18n.
- [x] **Upload UX redesign + genre search** — UploadView/Upload tabs получили
  iOS-like polish, добавлено умное combobox с ES-backed fuzzy hints и
  create-new-genre flow, плюс haptic feedback и аккуратные микро-анимации.
- [x] **Upload: profile-owned artist flow** — `one account -> one artist`
  ownership (backend by user id), unique-name enforcement with migration
  auto-dedupe, auto-rename owned artist on `display_name` update, and
  UploadFileTab mode switch (`I am this artist` vs manual artist).
- [ ] **Home recommendations: richer highlight endpoint** — добавить
  отдельные данные для крупной карточки главного экрана: editorial label,
  reason/highlight metadata, стабильный hero image и компактные carousel
  controls. Реализовать отдельным backend/frontend проходом после review
  границ Backend/PrivateCore; текущий UI использует существующие
  `continue` / `personalized` / `user_choice` / fallback tracks.

## Админка / альбомы (2026-05-04)

- [x] **Admin: редактирование альбомов в UI** - колонка `tracks.album_position` (миграция `0071`), порядок треков в публичном `GET /albums/{id}`, API `/api/v1/admin/albums` (список, детали, PATCH, обложка, add/remove/reorder треков), маршруты `/admin/albums` и `/admin/albums/:albumId` (capability `tracks.manage`).
- [x] **Admin: плейлисты** - API `/api/v1/admin/playlists`, UI `/admin/playlists` и `/admin/playlists/:playlistId` (метаданные, состав, порядок; уплотнение `playlist_tracks.position` после удаления).
- [x] **Admin: artist catalog editor UX (2026-05-05)** - `ArtistCatalogEditor` release metadata + cover upload, per-track title/artist/description/cover, paged «all tracks» list; API `POST /api/v1/admin/tracks/{id}/cover`, `POST .../catalog/releases/{id}/cover`.
- [x] **Playback health / auto-hide (2026-05-07)** — миграция `0083`, PrivateCore `playback_health_policy.py`, события `track_playback_failure_events`, колонки `tracks.playback_*`, авто-`playback_suppressed_until`, фильтр публичных выборок, запись при исчерпании fallback и ошибках upstream-прокси, админ-списки + вкладки в `TracksRoute`, API `playback-health/*`, снятие авто-hide; admin PATCH поддерживает `sc_url` / `source_url` / `canonical_source_url`.
- [x] **Admin playback health UI (2026-05-07)** — модалка «Источники» (редактирование/очистка URL), серверная **Проверить** (`POST .../verify`), **Сброс меток**, **Полное восст.**, **Снять auto-hide**; PATCH с `exclude_unset` и очистка URL в `admin_update_track`.
- [x] **Lyrics: catalog без ASR-бэкоффа без текста + метка miss + sweep (2026-05-07)** — колонка `tracks.lyrics_catalog_miss_at`, `catalog_only` не эскалирует на Whisper/SpeechKit при miss; текст без таймкодов сохраняется как plain-only; карточка/`TrackResponse.has_lyrics` по непустому plain text; импорт и глобальная очередь через `LyricsService.enqueue_background_lyrics`; часовая `lyrics_discovery_sweep_task` в `scheduled_jobs`; фильтр `GET /admin/tracks?lyrics_catalog_miss_only=1`; UI: скрытие кнопки «Текст» и вкладки Now Playing без текста.

## Подписки на артистов и статистика (2026-04-30)

- [x] **artist_follows** - миграция `0068`, модель, репозиторий, сервис, API: `POST/GET /artists/{id}/follow`, `GET /artists/{id}/follow/status`. Авто-подписка при онбординге (`save_preferences`). `follower_count` + `monthly_listeners` в `ArtistDetailResponse`.
- [x] **Рекомендации по подпискам** - `RecommendationService._build_user_prefs` объединяет `preferred_artist_ids` (онбординг) и `followed_artist_ids` (follows) через `dict.fromkeys` (порядок + дедупликация).
- [x] **Похожие артисты через SC-станции (2026-05-01)** - `ArtistCatalogRepository.get_similar_artist_ids_from_stations` извлекает artist_ids из треков «похожее»-станций любимых артистов; передаются в `UserPrefs.similar_artist_ids` (PrivateCore); scoring: 0.5x vs прямых фаворитов. `sync_artist_similar_station_task` + on-follow/onboarding триггер в `ArtistFollowService._enqueue_station_sync_if_stale` (порог `artist_station_stale_threshold_days=7`).
- [x] **Авто-очередь full catalog sync на follow/onboarding (2026-05-04)** - `ArtistFollowService` теперь ставит `sync_artist_catalog_task` для stale-артистов (порог `artist_catalog_full_sync_stale_threshold_days=30`) и дедуп enqueue через Redis lock (`artist_catalog_enqueue_lock_ttl_seconds`), чтобы не спамить Taskiq при массовых подписках.
- [x] **Активные слушатели в месяц** - `artist_monthly_stats` таблица, `ArtistStatsRepository.count_active_listeners` (live из `listen_events`), `GET /artists/{id}/stats/listeners` (текущий месяц + история).
- [x] **Снапшот за прошлый месяц** - Taskiq задача `snapshot_monthly_artist_stats_task` (запускается вручную или через внешний cron `0 2 1 * *`). `ArtistStatsService.snapshot_all_artists`.
- [x] **Cron-расписание снапшота** - миграция `0069` seed'ит запись в `scheduled_jobs` с cron `0 2 1 * *` (TaskiqScheduler / scheduler_service).
- [x] **Расширить `artist_monthly_stats`** - миграция `0070`, колонки `total_plays`, `total_likes`, `total_followers`; `ArtistStatsRepository` + `ArtistStatsService` + схема + frontend types. Chart в ArtistView показывает данные в tooltip.
- [x] **Frontend: карточка артиста** - `follower_count`, `monthly_listeners` и кнопка «Подписаться» уже реализованы в ArtistView (2026-04-30).
- [x] **Frontend: отдельная страница статистики** - `/artist/:id/stats` с полноценными recharts-графиками (total_plays, total_likes, total_followers по месяцам). Базовый bar-chart unique_listeners уже есть в ArtistView.
- [x] **Бот: плеер - источник «Подписки»** - источник `follows` добавлен в inline-плеер; `GET /users/me/followed-artists/tracks` (backend), `get_followed_artists_tracks` (bot client), кнопка «Мои подписки» в меню.

## Соответствие 152-ФЗ / ПДн (backlog, продукт + инженерия)

- Перед публичным запуском: **согласовать с юристом/DPO** фактическую обработку ПДн с требованиями 152-ФЗ (и смежное): основания, при необходимости уведомительный/регистрационный контур, субпроцессоры (email, observability, ASR-облака, бэкапы), трансгран, сроки хранения, запросы субъектов, реагирование на инциденты. Опора на `LEGAL.md`, `docs/legal/PRIVACY_POLICY.md` (сейчас draft).
- **Скорректировать функционал** по итогам: ретеншн/удаление, минимизация полей, kill-switch внешних API, согласованность логов и бэкапов с политикой. Не полагаться на внутренние id вместо `telegram_id` как на «анонимизацию», сохраняются операторские обязанности.
- См. также: `docs/project_context.md` (compliance), `AGENTS.md` (Legal readiness).

## Критичные / Инфраструктура

- Система бэкапов: PostgreSQL + Redis + configs (локально)
- Система логирования: JSON structlog + Docker log rotation (тонкая настройка: `REDACT_LOGS`, `REDACT_LOG_IDENTIFIERS`, `LOG_THIRD_PARTY_LEVEL`)
- Outbound Tor pool: по умолчанию выкл., `TOR_POOL_ENABLED=true` - opt-in
- Taskiq worker: graceful shutdown (`WORKER_SHUTDOWN`: cancel `import_queue_dispatcher` / `lyrics_global_orchestrator` background tasks, `close_es` в воркере) - 2026-04
- Docker Compose `worker` service: taskiq modules aligned with root `main.py` (imports, lyrics queue, snippets) - 2026-04
- SoundCloud `get_stream_info`: progressive manifest 404 - try HLS transcoding before 502; other upstream HTTP errors - 502 - 2026-04-29
- Audio-compute worker download: OTT with `proxy=1` so Backend proxies SoundCloud progressive streams (worker no longer GETs time-bound CDN URL directly; avoids 403) - 2026-04
- LyricsJob pull claim: admin profile `remote_whisper` now maps to the same queued rows as `gpu_full` (TIER_PROFILE_MAP); tier availability heartbeat counts both - 2026-04-29
- Mini App плеер: после сбоя Hls.js fallback `GET /audio` отдавал 302 на M3U8, Chrome в `<audio>` M3U8 не декодируется - добавлен `?force_progressive=true` (прокси MP3 с S3) и хелпер `trackProgressiveAudioUrl` в плеере / оффлайн-кэше / админ-превью - 2026-04-27
- Плеер: после ошибки `getStream` карточка вызывала только `togglePlay` по пустому audio - повторное нажатие Play перезапускает `playTrack`; начальный HLS без fallback - reject; dev/admin: override URL потока в карточке (sessionStorage) - 2026-04-29
- Lyrics cascade: preserve **root** worker failure in `cascade exhausted` message (not only last tier gate, e.g. `speechkit_disabled`); `lyrics_jobs.request_with_sync` / `request_bypass_cache` for fallback dispatch; log `audio_compute_worker_fail` - 2026-04
- [x] **Taskiq/cron: weekly batch stale station sweep (2026-05-02)** - `ArtistCatalogRepository.find_stale_station_artist_ids(threshold_days)`; `sync_stale_stations_batch_task` в `artist_catalog_sync_worker` (enqueue per-artist `sync_artist_similar_station_task`); миграция `0069` seed'ит `scheduled_jobs` с cron `0 3 * * 1` (Пн 03:00 UTC).
- **Полное копирование аудиофайлов (MinIO) на удаленный backup-VPS**
  - Подключение к отдельному серверу по SSH
  - `mc mirror` MinIO -> remote, инкрементально
  - Шифрование трафика, ключевая аутентификация
  - Настройка через `.env` (`BACKUP_REMOTE_HOST`)
  - UI в админ-панели: запуск/статус/расписание бэкапа
- Админ-панель (frontend): Раздел управления бэкапами
  - Просмотр списка бэкапов, размер, даты
  - Ручной запуск полного бэкапа
  - Настройка расписания
  - Статус последнего бэкапа (OK / FAIL)
  - Кнопка восстановления (с подтверждением)

## Админ-панель (выполнено)

- **Полноценная админ-панель** (Phase 1-5)
  - Backend `/api/v1/admin/*`: auth (TOTP onboarding с QR, login, device approval, step-up, refresh, logout), dashboard, tracks/users/complaints (без inline SQL), tasks (lyrics_jobs + compute_jobs + Taskiq queues + worker audit), logs (Loki proxy), metrics (Prometheus proxy), system (services health, containers, migrations, feature flags на app_settings), audit (admin_actions_log + CSV export), security (login attempts, locked users, lockout release), WebSocket для realtime
  - Многоуровневая защита: admin TOTP + device binding + pending_device email-flow + step-up для критичных действий + Telegram-алерты + короткие 15-мин сессии + rotating refresh + CSRF double-submit + строгий CSP + brute-force lockout
  - Observability: Prometheus + Grafana + Loki + Tempo + cAdvisor через `docker-compose.observability.yml`, `app/core/observability.py` (metrics/tracing/Sentry с PII-фильтром), расширенный `/health/deep` (db/redis/s3/taskiq/loki/prometheus)
  - Frontend `frontend/src/admin/` как chunked secure bundle: AdminApp, routes, layout, recharts графики, TanStack Query/Table, Zustand stores, semantic state-tokens только для StatusPill (см. design-system.md)
  - Документация: `docs/admin/{README,security,onboarding,testing,nginx-example.conf}`
- UX (2026-04): `AdminPromptProvider` (модалки вместо `alert`/`confirm`), i18n для строк админки, динамический заголовок раздела в topbar, выдвижное меню на «узком» вьюпорте (<720px), сортировка колонок в `DataTable` на Users/Tracks/Tasks/Artists/queues
- Post-ingest фон: enqueue compute + lyrics cascade при новом треке (upload / SC import / telegram import); массовый SC - paced lyrics без дубля; админ Tasks - таблица compute + источник lyrics job - 2026-04
- Перенести admin-security policy in PrivateCore (см. выше)
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
- [~] **Сканирование загрузок: режим `lightweight` или `clamav`**
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

- **Плейлист «Выбор пользователей» + счетчик `play_count` (2026-04-27):** PrivateCore `playcount_policy` (qualify, `rank_user_choice_tracks`); `GET /api/v1/recommendations/user-choice`, секция `user_choice` в `GET /api/v1/recommendations/home`; `PublicPlayCountService` + Redis 24h-дедуп; залогиненные - сигнал listen; гости - `POST /api/v1/tracks/{id}/play`
- **Рекомендации (2026-04 / RU-first для всех):** `recommendation_language_policy` - `RU_STRATIFICATION_ALWAYS`, `DEFAULT_CYRILLIC_STRATA_RATIO`, cold-start affinity; `_merge_language_affinity` / похожие / fallback home / user-choice - стратифицированные пулы; см. `docs/private-boundary-inventory.md`
- **Recsys - Track A / Phase 1 (2026-04):** гибрид `genre_samples` + очередь 15s превью, `GET .../preview-queue`, track-preview сегмент, админ-CRUD и capability `recsys.genre_samples.manage`
- **Recsys - Track B1 / Phase 5 Backend (2026-04):** миграция `0060` (таблицы features/similarity), internal API `/api/v1/internal/compute/*` (HMAC), `compute_results_router`, post-upload enqueue, CLI `python -m app.cli.compute_backfill`, `track_features_builder` + тесты
- **Recsys handoff (2026-04-27):** удален каталог `docs/recsys-parallel/`; ссылка в `project_context` убрана; тест `test_backfill_dry_run_uses_patched_session` чинит патч `AsyncSessionLocal` в `app.cli.compute_backfill`
- **Immediate: перенести auth/email policy в PrivateCore**
  - `account_linking_service`: `_LINK_TTL`, `_LINK_EMAIL_TYPE`, `_LINK_PREFIX`, `_LINK_TG_PREFIX`
  - `account_linking_service`: импортировать `is_disposable_email` из `dotsound_private_core.services.abuse`
  - `email_auth_service`: `_2FA_SESSION_TTL`, `_MAGIC_LINK_TYPE`, `_2FA_SESSION_TYPE`, `_ML_PREFIX`
  - `email_auth_service`: policy генерации fallback OTP (6-значный код) перенести в helper PrivateCore
  - `email_sender`: текст TTL fallback-кода строится от `FALLBACK_CODE_TTL`, без hardcoded `5 minutes`
- **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - Перенесен inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` доступны через `AdminRepository`/admin endpoints
- **Перенести admin-security policy в PrivateCore**
  - Создан `dotsound_private_core/services/admin_security_policy.py` с константами и decision-функциями
  - Удален временный stub `app/core/_admin_security_constants.py`
  - Все backend модули (admin_auth_service, admin_device_service, admin_alert_service, admin_manifest_service, ws.py, observability.py) переключены на импорт из PrivateCore
  - Добавлен endpoint-контракт `ADMIN_ALERT_ENDPOINT` в `dotsound_private_core/contracts/internal_api.py` + URL builder `admin_alert_url` в `internal_bridge.py`
  - Реализован `handle_admin_alert` в DotSoundBot (`bot/api/internal.py`) с allowlist `chat_id` и HTML-escape
  - Тесты: PrivateCore 88 admin-related, Bot 9 admin alert, Backend smoke + repo

## Продукты: пять спринтов (реализовано в Backend, 2026-04)

- S1 **Radio** - `GET /api/v1/tracks/{id}/radio` (каталог + YouTube mix/search + materialize), флаги `RADIO_*` в `config`, политика `dotsound_private_core.services.radio_policy`
- S2 **Co-listen** - `co_listen_rooms` + `POST/GET/PATCH /api/v1/colisten/rooms`, `WS /api/v1/colisten/ws/{room_id}` (Redis pub/sub), `dotsound_private_core.services.colisten_policy`
- S3 **Author stats** - `GET /api/v1/tracks/{id}/author-stats` (владелец), `listen_events` + `play_count` + лайки, `author_stats_policy` (округление)
- S4 **Плейлисты коллаб** - `playlist_collaborators`, `playlist_invite_tokens`, `POST /playlists/{id}/invites`, `POST /playlists/invites/accept`, правка `PlaylistService` для **editor** коллаб
- S5 **Сниппеты** - `track_snippets`, `POST /tracks/{id}/snippets`, `snippet_worker` (Taskiq + ffmpeg), `snippet_policy` + gating `catalog_type`
- **Follow-up:** Mini App / бот (кнопки radio, colisten, UI статистики, accept invite), e2e-тесты, Prometheus-метрики `radio_*` / runbook; юридический sign-off third-party + сниппетов (см. `LEGAL.md`). Миграция: `alembic upgrade 0056`.

## Плеер в боте

- Inline аудио-плеер (3 трека, editMessageMedia)
- Выбор источника: Мои / Лайки / Лента
- file_id кэш в Redis
- Предзагрузка следующей пачки
- Фильтрация треков без файлов (playable_only)
- Расширить источники: плейлисты, подписки, рекомендации
  - Для источника "Рекомендации": алгоритм ранжирования и скоринг в PrivateCore, Backend/бот - адаптеры выдачи
- Shuffle / Random режим

## Интернационализация (i18n)

- **Английская версия сайта (базовая)**
  - `react-i18next` + `i18next-browser-languagedetector`
  - JSON-каталоги `ru.json` / `en.json` (ключевые экраны: Auth, Home, Nav, Search, Liked, Upload, Profile, Playlists, Settings)
  - Telegram `language_code` custom detector
  - Переключатель языка в SettingsSheet
  - Поле `locale` в модели User + PATCH /users/me
  - Alembic миграция `0024`
- i18n: мигрировать оставшиеся ~35 .tsx файлы на `useTranslation`

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

- Установка на устройство: `isTelegram()` по `initData` / user; `InstallPrompt` (iOS Safari / прочий iOS, Chromium `beforeinstallprompt`, fallback без BIP); manifest `id`, один `link` manifest
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
  - **Управление**: экран "Скачанные" (список, занято места, кнопка удаления); лимит по объему (настраиваемый, ~500MB)
  - **Оффлайн-режим**: Service Worker перехватывает `/api/v1/tracks/{id}/audio` и `/hls/` - если есть в кеше, отдаем локально
  - **Плеер**: `playTrack()` проверяет Cache API перед сетевым запросом; оффлайн-треки играют без интернета
  - **Синхронизация**: при появлении сети - sync play counts (Background Sync API); обновление метаданных
  - **Ограничения**: HLS-треки кешировать как один файл через fallback endpoint `/audio`; DRM/лицензирование не применяется (UGC-платформа)
- **Грамотный единый плеер для разных платформ / источников**
  - Привести к единому UX `ugc`, `licensed`, `external_reference`
  - Разделить `access_mode`: `internal_stream`, `third_party_stream`, `official_embed`, `external_link`
  - Показать пользователю понятный режим доступа: наш стрим / внешний поток / открытый источник
  - Для каждого источника определить допустимые механики playback и ограничения по Terms
  - Гармонизировать `PlayerContext`, `TrackCard`, `TrackCardSheet`, deep links и search/import UX
  - Не смешивать в UI внешний reference и внутренний storage-backed трек как один и тот же тип воспроизведения

## Видео к трекам

- Загрузка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- Удаление видео (`DELETE /tracks/{id}/video`)
- Выдача видео (`GET /tracks/{id}/video`, proxy из S3)
- UI: Фоновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- **Оптимизация/сжатие видео**
  - Taskiq task `transcode_video` (`video_transcoding.py`): FFmpeg H.264 + AAC
  - Max 720p, CRF 23, `-preset medium`, `-movflags +faststart`
  - Thumbnail генерация (FFmpeg `-ss 1 -frames:v 1`)
  - `video_processing_status` + `video_thumbnail_key` на Track (миграция `0023`)
  - Upload -> temp S3 -> queue -> async transcode -> update status
- Увеличить лимит загрузки до 50MB (из PrivateCore `MAX_VIDEO_BYTES`)
- Адаптивный HLS для видео (как для аудио)
- Ограничение длительности видео (Canvas-стиль или длина трека)
- Учет видео в storage quota пользователя

## Метаданные трека

- Изменение `is_public` после загрузки (PATCH)
- Загрузка/замена обложки
- Загрузка/удаление видео
- Текст песни (plain text) + синхронизированные тайм-коды
- **Редактирование title, artist, genre после загрузки**
  - `TrackUpdateRequest` расширен (Optional поля title/artist/genre/description)
  - `TrackRepository.update_track()` + `TrackService.update_track()`
  - PATCH endpoint обновлен: принимает любую комбинацию полей
- Поле `description` в модели Track (TEXT, nullable)
  - Alembic миграция `651109411149`
- **Автоопределение текста песен (lyrics auto-detection)**
  - Весь пайплайн в PrivateCore (черная коробка)
  - Backend: тонкий адаптер (S3 download, вызов PrivateCore, сохранение в БД)
  - Выбор режима: "Определить текст" (без таймкодов) / "Определить текст + таймкоды"
  - Без таймкодов: synced_lines хранятся в БД, переключение без пересчета
  - Редактирование автосгенерированного текста, source manual/auto
  - Поддержка внешних треков без аудио (только текст)
  - Миграция 0030: колонка source в track_lyrics
  - Taskiq-задача generate_lyrics_task
  - API: POST /lyrics/auto, GET /lyrics/auto/status
  - Frontend: кнопки автогенерации, toggle таймкодов, i18n
  - Re-define fix: админ-кнопки с `bypass_cache=true` + расширенные debug-логи в карточке (шестеренка)
  - Search fallback fix: при miss по `(artist,title)` делаем retry по `title-only` и сохраняем cache alias
  - Stability fix (2026-04-25): remote catalog-align теперь получает `audio_seconds` от compute-worker для корректной шкалы времени; добавлен защитный rescue от схлопнутой line-sync таймлинии (когда строки прилипают к одному позднему якорю), плюс retry на отправку `result/fail` из worker.
- **Auto-lyrics: вынос тяжелой обработки на внешний GPU-сервис (далекое будущее)**
  - Отдельный сервер/сервис с GPU для обработки аудио
  - Backend отправляет аудиофайл во внутренний API PrivateCore, а PrivateCore уже сам решает, обрабатывать локально или вызывать внешний GPU-сервис
  - Интеграция через существующий `lyrics_provider` в PrivateCore (внешние детали - внутри черного ящика)
- **Karaoke после catalog + remote ASR align (пока не делаем):** UI показывает режим «караоке» только при `word_times` на строках **и** `sync_quality === "word"` (`LyricsPanel.tsx`, `FullscreenLyrics.tsx`). Ветка `POST .../audio-compute/.../result` с `align_text_to_precomputed_asr_timed_words` сейчас пишет в БД **только** line-level строки + `sync_quality=line` - словесные таймкоды с воркера в сохраненный JSON не переносятся. На будущее: после align приклеить/распределить `word_times` к выровненным строкам каталога (из `asr_timed_words` или исходных `synced_lines` воркера) и при успехе выставлять `word`, чтобы караоке снова работал при эталонном тексте.
- Теги (`tags`, JSONB или отдельная таблица)
- BPM auto-detection (background task, `librosa` / `essentia`)
  - Извлечение фич/пороги confidence и decision rules в PrivateCore, Taskiq orchestration и запись результата - в Backend
- Waveform generation (pre-render формы волны для UI)

## Чат и комментарии

- Чат: DM, группы, WebSocket real-time
- Реакции, вложения, голосовые сообщения, цитирование
- WebSocket: Redis pub/sub, presence, typing indicators
- Комментарии к трекам: CRUD, голосование, пин, скрытие; Mini App - секция в `TrackCardSheet` для публичных треков; сервис - комментарии недоступны при `is_public=false`; ответы на комментарии (`parent_id`, дерево вложенности)
- [x] In-app уведомления: лайк комментария и ответ (`comment_like`, `comment_reply`), переход из панели уведомлений к комментарию (`focus_comment_id`, подсветка ветки) - 2026-04
- [~] Доработки чата (обсудить отдельно)

## Карточка артиста (multi-source)

- [x] **Каталог дискографии (SoundCloud) - phase 1:** миграция `0063` - `artist_catalog_releases`, `artist_catalog_release_tracks`, `artists.soundcloud_user_id`, `artists.soundcloud_permalink`; SQLAlchemy-модели; без HTTP/синка (след. этапы 2–3)
- [x] **Каталог дискографии - phase 2:** `SoundCloudService.list_user_albums` (пагинация `next_href`), `fetch_track_by_id`, `expand_playlist_stub_tracks`, `ensure_soundcloud_ids_for_artist` + `ArtistRepository.find_by_soundcloud_user_id`; без Taskiq / оркестратора каталога (phase 3)
- [x] **Каталог дискографии - phase 3:** `ArtistCatalogSyncService` (`sync_full_artist`, `sync_single_release`), `ArtistCatalogRepository`, Taskiq `artist_catalog_sync_worker` (`sync_artist_catalog_task`, `sync_artist_catalog_release_task`), `catalog_uploader_id`, `SoundCloudService.fetch_playlist_by_id` / `download_artwork_as_cover_key`; без публичных/admin HTTP-рутов (phase 4–6); перед синком - `try_autofill_soundcloud_user_id_for_artist` (permalink / профильные URL из `source_profiles`, иначе первый хит user search) - 2026-04-28; тот же autofill вызывается из `AdminArtistCatalogService` при постановке full/release sync в очередь (раньше enqueue отсекал `NULL` до воркера) - 2026-04-29
- [x] **Каталог дискографии - phase 4:** публичное чтение каталога `GET /api/v1/artists/{id}/catalog/releases`, `GET /api/v1/artists/{id}/catalog/releases/{release_id}` - `ArtistCatalogReadService`, расширение `ArtistCatalogRepository`, схемы `app/schemas/artist_catalog.py`, pytest `tests/app/api/v1/test_artist_catalog_releases.py`; admin каталог: `app/api/v1/admin/artist_catalog.py`, `tests/app/api/v1/admin/test_admin_artist_catalog.py`
- [x] **Каталог дискографии - phase 5 (mini app):** карточки релизов и экран релиза с ordered track list в `ArtistView`, API-клиент и типы; воспроизведение через `TrackList` / `TrackCard` - 2026-04-28
- [x] **Каталог дискографии - phase 7:** `catalog_sync_policy` (PrivateCore), лимиты в `ArtistCatalogSyncService`, cooldown постановки в очередь в `AdminArtistCatalogService` + 429 в admin API, `ArtistCatalogRepository.latest_synced_at_for_artist`, `SoundCloudService.list_user_albums` - `(albums, truncated)` - 2026-04-28
- Policy-exception для явного source attribution (`source_name` + `source_page_url`) зафиксирован в `docs/ai-boundary-policy.md` (Backend + PrivateCore)
- PrivateCore: расширен контракт `ArtistInfo` полями `source_profiles`, `primary_source_id`, `discography`
- Backend: добавлены `artists.source_profiles` (JSON) и `artists.primary_source_id` (миграция `0039`)
- Backend API: `ArtistDetailResponse` и `/api/v1/artists/{id}` возвращают `source_profiles` и `primary_source_id`
- Frontend ArtistView: горизонтальный переключатель источников под аватаром + рендер bio/meta/discography по выбранному источнику
- Frontend ArtistView: полноэкранный просмотр аватарки с закрытием по overlay / кнопке / `Esc`
- Frontend ArtistView: отдельная строка `Источник: <source_name>` с кликабельной ссылкой на страницу источника
- Регрессионные тесты обновлены:
  - PrivateCore `test_artist_info_provider.py`
  - Backend `test_artist_enrichment_service.py`, `test_artist_enrich.py`, `test_artist.py`

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
  - При проигрывании текущего трека - начинается буферизация аудио следующего трека в фоне
  - Скрытый `<audio>` элемент (`preloadAudioRef`) с `preload="auto"` загружает URL следующего трека
  - Для HLS: создать второй `Hls` instance, привязать к preload-элементу, дождаться `MANIFEST_PARSED`
  - При `playNext` - swap: preload-элемент становится основным, мгновенный старт без буферизации
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
- [x] Taskiq job для hard delete после 30 дней — `app/services/account_deletion_service.py` + `account_deletion_worker.py`, миграция `0078_user_hard_delete_anonymize_fks` (`messages.sender_id`, `track_comments.user_id` CASCADE → SET NULL), seed `daily-user-hard-delete` cron `30 3 * * *`; PrivateCore policy: `hard_delete_cutoff`, `build_anonymized_username`, `ANONYMIZED_DISPLAY_NAME`, `HARD_DELETE_BATCH_LIMIT`; комментарии и сообщения рендерятся как `Deleted user`; tests: PrivateCore +6, Backend +6 (2026-05-06).
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
  - Политики re-auth/cooldown/max-attempts для удаления страниц в PrivateCore

## Frontend / Mini App

- [x] Плеер / карточка трека / оверлеи: motion-токены, decay спектра при паузе, enter/exit (в т.ч. FullscreenLyrics), микро-виз в `PlayerBar` - 2026-04-29
- [x] Страница 404: контраст CTA, карточка, safe-area / адаптив - 2026-04-29
- **Покрытие Backend API клиентом:** инвентарь и приоритеты - `docs/api-frontend-coverage.md`; расширен `frontend/src/lib/api.ts`, исправлен `POST /users/me/avatar`, UI (OAuth disconnect, удаление аккаунта, похожие артисты), `adminApi.metricInstant`; регрессия - `scripts/check_openapi_frontend_coverage.py`
- Главная: CTA «Слушать/Play» - старт с первого трека плейлиста дня (дальше - существующий radio-prefetch в `PlayerContext`); карточка «плейлист недели» и экран `/weekly-mix` (API `weekly-playlist`).
- Восстановление позиции воспроизведения при перезапуске
- Монохром-фильтр в настройках
- Админ-панель: управление пользователями
  - Если добавятся баны/risk flags/anti-abuse actions, decision rules и пороги должны идти из PrivateCore
- Админ-панель: модерация контента
  - Пороги auto-hide/escalation и moderation policy держать в PrivateCore, панель - UI + вызовы Backend API
- Админ-панель: управление бэкапами (см. выше)

## Frontend оптимизация

- **Mini App (браузер): GPU / композитор** - смягчены токены стекла, фикс-панели `#nav` / `#player-bar` на `--glass-backdrop-fixed*`, липкий поиск на более легком blur; класс `ds-low-glass` при `prefers-reduced-motion` / `prefers-reduced-data`; без бесконечных splash/home; при play - легкий `pbPlayGlow` (откл. при reduce motion), статичный EQ в очереди; спектр на canvas ~12 fps, cap DPR, меньше столбцов - 2026-04
- **Waveform (карточка трека): снижение нагрузки на iGPU** - `setInterval` ~12 fps вместо RAF на частоте дисплея; буфер FFT без аллокаций каждый кадр
- **PlayerContext: CPU** - throttling обновлений `currentTime` в React (~10/s), flush при play/pause/seek/skip; виджеты и экраны без таймера переведены с `usePlayer()` на `usePlayerActions` / `usePlayerMeta`, чтобы не перерисовываться на каждый тик
- **SearchView: прогрессивная выдача** - `getTracks` / `searchSuggest` не ждут YouTube, Bandcamp, SoundCloud; внешние секции обновляются по мере ответа и могут отображаться до готовности блока «На платформе»
- **PlayerContext split (производительность)**
  - 3 контекста: `PlayerStateCtx` (currentTime, duration, isPlaying), `PlayerActionsCtx` (стабильные callbacks через useCallback), `PlayerMetaCtx` (track, volume, EQ, модалки)
  - 3 хука: `usePlayerState()`, `usePlayerActions()`, `usePlayerMeta()`
  - `usePlayer()` -- compat shim для плавной миграции
- **LikesContext оптимизация**
  - `useMemo` на value, `useCallback` на все функции
- **React Router (deep links, PWA)**
  - `react-router-dom` v7 (React Router)
  - Маршруты: `/`, `/search`, `/upload`, `/liked`, `/playlists`, `/chats`, `/chats/:id`, `/profile`, `/track/:trackId`
  - `BottomNav` через `useNavigate` + `useLocation`
  - `BrowserRouter basename="/mini_app"`
  - Browser back/forward, shareable URLs, deep links
- **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView, LikedView, PlaylistsView, ChatsView, ProfileView
  - `hls.js` в отдельный chunk (`manualChunks`)
  - `<Suspense>` обертка для route-level lazy loading
- **TanStack Query (API кеширование)**
  - Автоматический кеш, дедупликация, stale-while-revalidate
  - Постепенное внедрение (endpoint за endpoint)
- Типизация: убрать 5x `Promise<any>` в `api.ts`
  - `ImportJobResponse` + `ImportAudioInfo` в `types/api.ts`
  - `genre` + `description` добавлены в `Track` interface
- CSS: рассмотреть разделение `global.css` (~2700 строк)

## Backend API

- YouTube import/playback: fallback на auto-выбор формата в `yt-dlp` при `Requested format is not available` (без 422/503 из-за жесткого format-string)
- YouTube import/playback: fallback по client-профилям `yt-dlp` при anti-bot (`Sign in to confirm you’re not a bot`) + возврат 503 вместо 422 для временной блокировки
- **Elasticsearch (поиск + suggest)**: индексы треков/артистов, Taskiq reindex/backfill, `GET /api/v1/search/suggest`, поиск треков с `q` через ES + PG fallback, bool/should (strict + fuzzy) для треков/артистов и саджеста, counter `elasticsearch_query_total` (op/outcome) в `observability`
- `artist_link_backfill_task` / `track_artists`: дедуп по `canonical` (PrivateCore + `resolve_and_link`), `ON CONFLICT DO NOTHING` в `link_track`, `begin_nested` + `error`/`error_type` в backfill
- `LOG_THIRD_PARTY_LEVEL` / `apply_third_party_log_levels` - уровень `urllib3`/httpx/ES/SQL-эха отдельно от `LOG_LEVEL`; Taskiq воркеры тоже при старте
- playable_only фильтр в track listing endpoints
- internal-token endpoint с полной защитой
- WebSocket: событие player.state для синхронизации
- Пагинация liked tracks (backend + frontend)
  - Backend: `page`/`has_more` в `UserLikesResponse`
  - Frontend: `LikedView` с "Показать еще" кнопкой

## Юридический аудит: анализ конкурентов (UGC + ст. 1253.1)

> **Цель**: изучить каждый сервис из списка на 2 вещи:
>
> 1. Наличие web-плеера / API для стриминга - возможна ли ретрансляция аудио на DotSound (аналогично SoundCloud: звук передается пользователю, плеер наш, мы оболочка).
> 2. Политика, соглашения, правовая реализация - что можно адаптировать для DotSound (тексты оферт, дисклеймеры, процедуры takedown, формы загрузки с подтверждением прав).

### Категория 1: Прямые аналоги (UGC + информационный посредник)

- **Musify.club**
  - Web-плеер: есть ли публичный стрим/API, можно ли встроить
  - Юридика: пользовательское соглашение (ст. 1253.1), страница `/contacts/legal` (перечень лицензий с ООО «АдвМьюзик» и др.), процедура DMCA/takedown, форма загрузки
  - Выводы: что адаптировать для DotSound
- **4beat.ru**
  - Web-плеер: стрим, embed, API
  - Юридика: пользовательское соглашение, форма загрузки трека (какие галочки/подтверждения прав требуют), страница правообладателям
  - Выводы: что адаптировать для DotSound
- **QPlet.ru**
  - Web-плеер: стрим, публичный доступ к аудио
  - Юридика: условия загрузки, онбординг артиста, оферта
  - Выводы: что адаптировать для DotSound
- **Созвук (sozvuk.ru)**
  - Web-плеер: стрим, embed, API для треков
  - Юридика: публичная оферта (ст. 1253.1), как оформлены права при загрузке, политика удаления по жалобе
  - Выводы: что адаптировать для DotSound

### Категория 2: Крупные платформы с UGC-компонентом

- **VK Музыка (vk.com/music)**
  - Web-плеер: закрытый API, возможности ретрансляции
  - Юридика: лицензионное соглашение (`vk.com/terms/music`), Content ID, как разделяют лицензированный и UGC-контент, процедура жалоб
  - Выводы: что адаптировать для DotSound
- **Яндекс.Музыка**
  - Web-плеер: закрытый стрим, ранжирование UGC vs лицензированное
  - Юридика: условия загрузки пользовательской музыки, как UGC показывается ниже официального в поиске
  - Выводы: что адаптировать для DotSound
- **ZVUK (zvuk.com)**
  - Web-плеер: стрим, партнерская модель
  - Юридика: условия для артистов, договоры с дистрибьюторами, требования к правам
  - Выводы: что адаптировать для DotSound

### Категория 3: Серая зона

- **Зайцев.НЕТ (zaycev.net)**
  - Web-плеер: стрим, API, легальная модель (100% лицензии с 2019)
  - Юридика: путь от UGC к лицензиям - что заставило перейти, пользовательское соглашение (написано юристами), страница правообладателям, процедура 5-дневного takedown
  - Выводы: какие тексты/процедуры адаптировать для DotSound
- **TRULA-music (trula-music.ru)**
  - Web-плеер: плеер + виджеты для стримеров
  - Юридика: оферта (ст. 1253.1), узкая ниша - как оформляются права
  - Выводы: что адаптировать для DotSound
- **Muzofond.fm / LightAudio.ru / HitMo (антипримеры)**
  - Web-плеер: открытый стрим, скачивание mp3
  - Юридика: нет явных лицензий, ссылаются на «пользователи загрузили», периодические блокировки Роскомнадзора
  - Выводы: какие ошибки НЕ повторять

### Итоговый отчет (после анализа всех сервисов)

- Сводная таблица: сервис / web-API / возможности ретрансляции / юридическая модель / риски / что адаптировать
- Список конкретных текстов для адаптации: оферта, дисклеймер, страница правообладателям, форма загрузки с подтверждением прав
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
  - `reason_type`, `rightsholder_name`, `proof_url` теперь проходят через schema -> route -> service -> repository -> UI
- Обязательный акцепт условий при `UGC` upload
  - Checkbox в `UploadFileTab.tsx`
  - backend validation в `api/v1/tracks/user.py`
  - логирование версии условий в `track_upload_meta`
- Постоянные guardrails для агентов и docs
  - `AGENTS.md`
  - `docs/ai-boundary-policy.md`
  - `.cursor/rules/legal-readiness.mdc`
  - `.claude/hooks` + `.claude/settings.json`: блок опасных shell-patterns, блок секретов, SessionStart контекст
  - `.cursor/rules/shell-safety.mdc` + `.cursor/rules/session-start-context.mdc` для эквивалентных guardrails в Cursor
- Явно размечен current MVP external playback
  - В `Track` добавлены `access_mode`, `source_platform`, `canonical_source_url`
  - `SoundCloud` import помечает трек как `third_party_stream`
  - UI показывает внешний источник и режим доступа
- На уровне модели разделены категории треков
  - В `Track` добавлен `catalog_type`
  - Базовое разделение: `ugc`, `licensed`, `external_reference`
  - `SoundCloud` -> `external_reference`, `upload/telegram` -> `ugc`
- Опубликовать legal docs в самом продукте как отдельные доступные страницы
  - `/legal` стал hub-страницей
  - Добавлены маршруты `/legal/terms`, `/legal/privacy`, `/legal/copyright`, `/legal/upload-rules`
  - Upload и complaint flow теперь ссылаются на конкретные legal docs
- Разделить на уровне модели/API `UGC`, `licensed` и `external-source` треки, не полагаясь только на текстовые дисклеймеры
- Проверить current MVP с собственным playback поверх stream URL стороннего сервиса для текущего внешнего источника (`SoundCloud`) и зафиксировать residual risk
- Разделить обычные пользовательские жалобы и надлежащее уведомление правообладателя в отдельные UX и workflow
- Базово разделить обычные жалобы и уведомление правообладателя в UX
  - `ComplaintModal` поддерживает режимы `user` и `rightsholder`
  - Правообладательский режим требует доп. поля и отдельный текст
- Internal checklist для Terms внешних источников
  - `docs/legal/SOURCE_TERMS_CHECKLIST.md`
  - rule/docs привязаны к проверке external-source integrations
- Сделать тексты внешнего импорта и поиска более честными
  - `SearchView` явно помечает SoundCloud как внешний источник
  - Текст предупреждает, что после добавления трек идет как внешний поток стороннего сервиса

## DevOps / CI

- **Branch coverage 95% (4 репо):** `scripts/check_branch_coverage.py` + `pytest --cov-branch` / `coverage.json` - порог `percent_branches_covered` (см. Makefile / `AGENTS.md`). Выполнено: полный прогон и проверка gate в Backend/PrivateCore/Bot/ComputeWorker.
- GitHub Actions: lint + test на PR (Backend, Bot, PrivateCore)
- Автоматический деплой на VPS
- Расширенный healthcheck (`/api/v1/health/deep` - БД, Redis, S3)
- Health monitoring + alerting (uptime check, внешний)

## Sprint 0..9 редизайна (2026-04, single-pass)

- Bot: like/dislike - добавлен Bearer + правильный internal id
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
- Bot: throttling middleware подключен к callback и inline_query
- Bot: внутренний HTTP-сервер binds `127.0.0.1` (через config)
- Bot: HTML escape во всех форматерах (`base`, `audio`, `inline`, `stats`)
- Bot: единый `mini_app_url` (убран `backend_base_url` для WebApp)
- Bot: internal API возвращает opaque error codes
- Bot: глобальный `errors` handler с user-friendly fallback
- Bot: prefetched URLs используются в `_edit_audio_batch` (gap-less)
- Bot: Dockerfile multi-stage с PrivateCore из родительской директории
- Frontend: дизайн-токены в `tokens.css` (8pt grid, motion, type scale)
- Frontend: `components.css` с Press, Sheet, Skeleton, EmptyState стилями
- Frontend: `Press`, `Sheet`, `EmptyState`, `SkeletonList`, `OfflineBanner`
- Frontend: расширен Icon-set (more-horizontal, queue, chevron-up/down)
- Frontend: Unicode заменен на `<Icon>` в FullscreenLyrics, PlaylistsView, ComplaintModal, TrackCard, PlayerBar
- Frontend: `installTelegramThemeBridge`, `installViewportListener`, `setBackButton`, `haptic`, `hapticNotification`
- Frontend: PlayerBar v2 - overflow menu + breakpoints + skeleton hit-area
- Frontend: TrackCard переключен на `usePlayerMeta` + `usePlayerActions`
- Frontend: CoverImage с `loading="lazy"` + `width/height`
- Frontend: aria-label/aria-pressed/aria-current на ключевых контролах
- Frontend: `useConfirm` переписан с правильным unmount cleanup
- Frontend: index.html splash сокращен с 1800ms до 1200ms safety cap
- PrivateCore: README актуализирован, версия `0.2.0`, policy с bounded-transport exception
- Backend: `/api/v1/health/deep` (DB / Redis / S3 ping)
- Backend: `X-Request-ID` отдается в заголовке ответа
- Docs: `docs/design-system.md`, `docs/redesign-rationale.md`

---

*Последнее обновление: 2026-05-08 (TODO.md: кириллица и тире в повреждённых строках).*

## Session Updates (2026-05-06)

- [x] Admin dashboard UI refresh: interactive online history chart with range switch (15m/1h/6h/24h), trend badge, and additional RPS/latency cards in `frontend/src/admin/routes/DashboardRoute.tsx` + `frontend/src/admin/styles/admin.css`.
- [x] Mini App loading-screen stabilization: unified startup lifecycle between `frontend/index.html` and `frontend/src/App.tsx`, removed polling race, and smoothed splash animation in `frontend/src/styles/global.css` (including reduced-motion profile).
- [x] Frontend-wide animation stabilization pass: unified motion tokens/easing in `frontend/src/styles/tokens.css`, softened keyframes and interaction feedback in `frontend/src/styles/animations.css` and `frontend/src/styles/components.css`, plus stronger reduced-motion guards for looping effects.
- [x] Focused motion polish for core UX zones: smoother interactions/transitions in `frontend/src/components/PlayerBar/PlayerBar.tsx` and `frontend/src/styles/global.css` for PlayerBar, TrackCardSheet, and Home cards/carousels (reduced jitter, calmer active states, better reduced-motion fallback).
- [x] Admin UI pass for secondary routes: KPI cards + sparklines for Users/Tracks/Complaints, plus live-toggle and loading/empty chart states for Metrics and Dashboard.
- [x] Admin dashboard statistics: backend `/api/v1/admin/dashboard/stats` with period aggregations (today/7d/30d), plus frontend stats block with KPI cards and top tracks list.
- [x] Admin tabs analytics expansion: track analytics (popular tracks + uploads timeline) and admin activity analytics (actions timeline + top admins) with period filters in `Tracks` and `Users` routes.

## Session Updates (2026-05-07) — iOS Redesign 2026 stage closure

- [~] **Radio hero waveform A/B pass (iteration 1 / style 1, candidate saved)**: в `./mini_app/radio` переработан visual baseline «основная волна + зеркальное отражение» для более минималистичного эфира (тоньше профиль, мягче контраст/blur, аккуратное fade-затухание отражения, адаптив desktop/mobile); вариант сохранён как кандидат через css-модификатор `rh-radio-hero-wave-bg--style1`; `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 2 / style 2)**: активирован более плотный и энергичный `live radio` стиль (`rh-radio-hero-wave-bg--style2`) с усиленной основной волной и явно читаемым зеркальным отражением (повышены opacity/контраст и глубина fade-маски); `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 2 / reflection fix + priority)**: `style2` зафиксирован как приоритетный; в `Waveform variant="radio"` волна переведена на baseline-отрисовку (не центр), чтобы зеркалирование реально читалось, плюс разделительная «waterline» и усиленный reflection-layer в hero; `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 3 / ambient-futuristic)**: добавлен необычный atmospheric-стиль `style3` с контурными кривыми (`repeating-radial-gradient`), glow-волной и отдельным зеркальным слоем/затуханием; сохранена структура «основная волна + отражение», `prefers-reduced-motion` соблюдён (анимации выключаются), `npm run build` зелёный.
- [x] **Temporary disable: Spotify account import (OAuth)** — backend endpoint `POST /api/v1/import/spotify_account` now returns 503; frontend `PlatformImportMethodModal` disables Spotify "login via account" action and keeps previous OAuth/import flow commented for fast restore; Spotify URL import remains active.
- [x] **Frontend haptic softening pass**: in `frontend/src/lib/telegram.ts` all existing interaction points keep their current calls, but Telegram haptic now prefers `selectionChanged` (fallback `impactOccurred('light')`) and browser vibration fallback is reduced to near-minimal pulses so feedback is barely noticeable.
- [x] **Frontend startup watchdog for infinite splash**: `frontend/src/App.tsx` init flow now has a guarded `try/finally` + 9s watchdog timer that forces app bootstrap completion (`setIsInitialized(true)` and auth fallback) if init network calls stall, preventing permanent loading screen.
- [x] Frontend performance pass (GPU/CPU): adaptive `ds-perf-lite` profile auto-enabled for coarse-pointer/low-spec devices, reduced global glass blur/saturation tokens, disabled expensive decorative layers/looping effects (`glass` noise/highlight, player glow, nav glow, queue EQ, video pulse), and throttled `BeatPulse` updates to ~20 FPS; `npm run build` green.
- [x] Playback hotfix: для SoundCloud `stream` recovery теперь считает `HTTP 502` (кейс `transcoding_manifest_404` по всем форматам) восстановимым и запускает fallback/replace трека вместо немедленного фейла `502`; добавлен regression-тест `test_recovery_handles_soundcloud_502_as_recoverable` в `tests/app/api/v1/tracks/test_playback.py`.
- [x] **Stage E (Chat/TrackCardSheet) — visual rewrite**: ChatList rows wrapped in `LongPressMenu` (mute/pin/unpin/mark-unread/delete) with monochrome icons; ChatBubble переведён на `m.div` со spring-scale (own send) / fade-up (incoming), реакции через `MorphIcon` + `LongPressMenu`; ChatView rewrite — `glass--liquid` sticky header с `MotionPress`/`MorphIcon`, `AnimatePresence` для menu dropdown, локализация всех hardcoded строк (`redesign.tracks.*`); ChatsView large-title sticky header; TrackCardSheet — drag-down close (threshold 100 px), все action-buttons на `MotionPress` + `MorphIcon`. CSS: `frontend/src/styles/redesign-tracks.css`.
- [x] **ChatView WS-dedup + DevPanel вынос**: activity-poll и message-poll теперь fallback (skip при `isWSConnected()`), интервалы 4s/8s; ~210 строк inline-styled DevTools вынесены в `frontend/src/components/Chat/ChatDevPanel.tsx` (DEV-only через `import.meta.env.DEV`), стили — в `redesign-tracks.css` (`.re-chat-dev-*`).
- [x] **Stage B (Onboarding) — stories-style transitions**: `AnimatePresence mode="wait"` + direction-aware variants через `directionRef` (forward/backward по stepIndex), `useReducedMotion` → opacity-only. Все интерактивные элементы (artist cards, mood/genre chips, calibration play/like/dislike/skip, footer Skip/Next, OnboardingGenreScreen preview) переведены на `MotionPress`; `MorphIcon` для pause-overlay и heart (filled при like). Inline-стили заменены классами `.re-onb-*` в `frontend/src/styles/redesign-nav.css`.
- [x] **Stage A (FullscreenLyrics) — Apple Music polish**: добавлен sticky header с маленькой обложкой через `BeatPulse` (bpm от трека, active=isPlaying) + meta-блок (title/artist) + close-кнопка на `MotionPress`. Playback controls (prev/play/next) на `MotionPress` + `MorphIcon` (`pause`/`play` filled). Стили в `frontend/src/styles/redesign-player.css` (`.rp-now-fl-*`).
- [x] **i18n**: новые ключи в `frontend/src/locales/i18n_extra2_{ru,en}.json` под `redesign.tracks.*` (chat menu, chat header/status, chat empty/divider, TrackCardSheet close, message reactions).
- [x] **Final acceptance**: `npx tsc --noEmit` — clean; `npm run build` — clean (vite + bundle-hygiene + admin-bundle), PWA precache 33 entries.
- [x] **Stream 2/3 polish (Stage D / I)**: ProfileView (tabs+settings → MotionPress, локализованы 'profile.tabProfile/Import/Complaints'), PlaylistsView (back/share/copy/close/share-row/create-playlist → MotionPress), LikedView load-more → MotionPress, ListenerStats period chips → MotionPress, OfflineList (clear-all + play + remove → MotionPress), HistoryList (retry + play row → MotionPress), UploadStepDetails (artist-mode + lyrics-trigger → MotionPress), UploadComboBox (toggle/items/create → MotionPress).
- [x] **Stage F (Artist views) + cross-cutting motion polish**: ArtistView — back/avatar/follow/snippet/source-tabs/admin-actions/bio-toggle/bio-more/catalog-cards/similar-arrows/similar-cards/listeners-toggle переведены на `MotionPress` + `MorphIcon` для play/pause превью, локализованы `redesign.artist.stopPreview/listenSnippets/sourcePlatform`; ArtistCatalogReleasePanel + ArtistAvatarViewer — back/close на `MotionPress`; AuthorView — back/follow на `MotionPress` + `Icon`, эмодзи `'👤'/'‹'/'✓'/'+'` заменены `Icon` (`user`/`chevron`/`check`/`bell`), inline-стили вынесены в CSS, hardcoded строки локализованы (`author.*`, `common.back`). Подмазаны pre-existing TS errors в AlbumView/PlaylistView/ExternalAlbumView/ExternalTrackView/GenreView (`return () => setBackButton(false)` → корректный void cleanup) и `'genre'` → `'genre_mix'` в `usePrefetchTracks`.
- [x] **Stage A overlays + Equalizer + Settings + Comments + Auth**: LyricsPanel (action-row + redefine/auto choice grids на `MotionPress`, локализация `lyrics.detectAuto/enterManually/redefineHeader/redefineTextOnly/redefineWithTiming/redefineNeedsAudio`), LyricsEditor (cancel/back/undo/seek-±5/play-pause/save-text/save-sync на `MotionPress` + `MorphIcon`), Equalizer (header chip/reset/close + preview-toggle + track-picker + presets на `MotionPress` с `MorphIcon` для play, локализация `equalizer.*`), SettingsSheet (back/close/EQ/openInBrowser/installAsApp/aboutApp/logout/test-sound/test-haptic на `MotionPress`), ComplaintModal (close/mode-toggle/submit на `MotionPress`), CommentCard (reply/menu/vote/delete/pin/hide/hideForMe на `MotionPress`), CommentInput (send на `MotionPress` с локализацией placeholder), CommentSection (reply-cancel на `MotionPress`), TelegramAuth + EmailAuth (все кнопки на `MotionPress`, эмодзи `✓` убран из success-icon). Pre-existing синтаксические ошибки `)` после `showIsland({...})` в TrackCard.tsx и TrackCardSheet.tsx исправлены, лишние `toast` deps в useCallback убраны.
- [x] **CSS уборка**: `redesign-artist.css` (`.rf-artist-snippet-wrap/btn/audio`, `.author-loader`, `.author-section-header`); `global.css` (`.eq-reset-confirm-label`, `.le-fs-save-btn`, `.lyrics-choice-back`, `.lyrics-choice-btn--disabled`); `i18n_extra2_{ru,en}.json` JSON-syntax bug `}` → `},` перед `"achievements": {}` пофикшен.
- [x] **Final acceptance (batch 2)**: `npx tsc --noEmit` — clean; `npm run build` — clean.
- [x] **Search screen blank-state fix**: восстановлен `SearchView` с discover empty-state (`/recommendations/discover`), табами `All/Tracks/Artists/Playlists`, и рендером результатов каталога + внешних источников; проверено через `npm run build`.
- [x] **Search discover genres polish**: `GET /recommendations/discover` теперь отдает `cover_key` для genre cards (по top-track в жанре), `SearchView` использует cover + визуальный fallback, блок `Ваши жанры` приведен к общему UI-стилю.
- [x] **Genre click search correctness**: добавлен явный `genre`-фильтр в `GET /api/v1/tracks` (route/service/repository), `SearchView` при клике по жанру передает `genre` в `api.getTracks`, чтобы выдача шла по жанру, а не только по title/artist.
- [x] **Search: dedicated Genres selector tab**: добавлена вкладка `Жанры` в `SearchView`, подгрузка каталога жанров через `GET /api/v1/tracks/genres`, и выбор жанра из вкладки с переходом к выдаче по `genre`-фильтру.
- [x] **Search genres UX + correctness finalization**: при клике на жанр активируется вкладка `Жанры`, в ней отображается счетчик `N треков в жанре`, и список треков этого жанра; в жанровом режиме отключено подмешивание `searchSuggest`-треков, чтобы не попадали нерелевантные результаты.
- [x] **Search genres stability + scalable list UX (2026-05-07)**: в `SearchView` жанровый режим изолирован от текстового поиска (защита от out-of-order ответов), добавлены алфавитная сортировка жанров, отдельный поиск по жанрам и поэтапная подгрузка (`Показать еще`) вместо моментального рендера всего списка чипов.
- [x] **Track card waveform + seek smoothness (2026-05-07)**: волна убрана из `PlayerBar` (нижнее состояние), в `TrackCardSheet` показывается только в открытой карточке и только при `isPlaying`; `WaveformBar` переведен на clip-based плавное заполнение прогресса; seek-индикаторы в `PlayerBar`/`TrackCardSheet` сглажены и убран визуальный «шлейф» у thumb; `npm run build` зеленый.
- [x] **PlayerBar volume quick entry (2026-05-07)**: в мини-плеер добавлена отдельная точка входа `volume` (иконка `volume-off/low/high`) с popover-слайдером `0..100%`, чтобы регулировать громкость без открытия карточки трека; закрытие по клику вне/`Esc`; стили в `frontend/src/styles/components.css`; `npm run build` зеленый.
- [x] **PlayerBar volume UX follow-up (2026-05-07)**: popover громкости переведен в вертикальный формат (вертикальный слайдер + компактный стек), а кнопку громкости перенесена ближе к транспортным контролам (перед like), чтобы доступ был быстрее в мини-плеере; `npm run build` зеленый.
- [x] **Hide YouTube tracks from public surfaces (2026-05-07)**: backend filters now exclude `source_platform/imported_from == "youtube"` from track lists/search/recommendation pools/playlists/likes/library and `TrackService.get_track` returns hidden for YouTube entries, so existing DB records are no longer shown in Mini App/API public flows.
- [x] **TrackCard: remove uploader block (2026-05-07)**: удалён блок «кто добавил трек» (аватар+ник) из `TrackCardSheet`; в backend `TrackCardResponse` больше не возвращает `author`, `CardService` перестал подгружать пользователя для карточки; обновлены frontend типы `TrackCardResponse` и schema-тесты `tests/app/schemas/test_card.py`.
- [x] **PlayerBar progress sync fix (2026-05-07)**: устранён рассинхрон верхней seek-линии и нижней glass-заливки в мини-плеере — оба слоя теперь используют единый `--progress` без двойного сглаживания, фон `#player-bar::after` выровнен по геометрии thumb (`--pb-fill` с компенсацией половины thumb), убраны рывки от hover/tap изменения толщины seek, добавлены согласованные WebKit/Firefox стили трека/прогресса/ползунка; `npm run build` зелёный.
- [x] **Ultra-smooth seek animation pass (2026-05-07)**: `PlayerBar` и `TrackCardSheet` переведены на локально сглаженное обновление прогресса через `requestAnimationFrame` + `getPreciseTime()` (плавнее fill/thumb/time без ступенчатости). Для `tcs-seek` увеличена зона нажатия (расширенный hit-area по вертикали) без визуального утолщения трека; сборка `npm run build` — зелёная.
- [x] **Radio disc swipe + playback-only motion (2026-05-07)**: `RadioView` теперь анимирует круговую обложку только при фактическом воспроизведении, поддерживает свайп влево/вправо в radio mode для переключения треков и slide-переход диска; `npm run build` зелёный.
- [x] **Radio hero wave background polish (2026-05-07)**: для `./mini_app/radio` в `rh-radio-hero__inner` добавлен размытый full-width wave-layer на базе `Waveform` (двойной слой + градиент), визуально по аналогии с волной карточки трека; `npm run build` зелёный.
- [x] **Radio hero wave expression pass (2026-05-07)**: усилил радио-визуал волн — multi-layer (`Waveform` x3) с разной частотой/плотностью баров, более контрастным градиентом, live-режимом `rh-radio-hero-wave-bg--live` и мягким drift/breathe движением для более «эфирного» радио-ощущения; `npm run build` зелёный.
- [x] **Radio hero waveform structure correction (2026-05-07)**: по фидбеку переделан фон радио в схему «одна основная волна + её отражение» (mirror), убраны лишние слои, обновлены частота/плотность формы (`bars=30`) и адаптивная высота через `clamp` для desktop/mobile; `npm run build` зелёный.
- [x] **Radio waveform visual-only refinement (2026-05-07)**: убрано любое «качание» фона и переделан именно силуэт волны для радио (`Waveform variant="radio"`: более собранный профиль с центральным акцентом, статичный render + mirror reflection), адаптив сохранён для desktop/mobile; `npm run build` зелёный.
- [x] **Radio next-track compact block (2026-05-07)**: блок настроений в `RadioView` деактивирован через TODO-комментарии, вместо него на `./mini_app/radio` показывается компактная карточка «Следующий трек» с обложкой, названием и артистом из очереди `PlayerContext`; `npm run build` зелёный.
- [x] **Radio paused pulse stability (2026-05-07)**: `BeatPulse` получил явный `data-beat-active`, а radio disc отключает `transform/transition` в paused-состоянии, чтобы обложка не дёргалась при паузе; `npm run build` зелёный.
- [x] **Mix views i18n + API typing cleanup (2026-05-07)**: `DailyMixView`/`WeeklyMixView`/`UserChoiceView`/`WeeklyTopView` переведены с hardcoded share-строк на `useTranslation` (`redesign.library.*` + `redesign.home.mixShareAria`), а в `frontend/src/lib/api.ts` убраны inline response-shapes в пользу типизированных контрактов `UserListeningStatsResponse`, `AdjacentTracksResponse`, `TrackQueueResponse`, `HomePageResponse` из `frontend/src/types/api.ts`.
- [~] **Endless radio anti-loop hardening (2026-05-07)**: переработан `build_radio_queue` в PrivateCore (seed-lock старт, микс unseen/favorite/rediscovery/similar, анти-повтор треков по недавней истории, cooldown артистов), backend radio cache теперь учитывает `exclude_ids` fingerprint, добавлен skip-guard `1 req/sec` с возвратом last queue для `GET /api/v1/recommendations/radio` и `GET /api/v1/tracks/{id}/radio`, лимит `exclude_ids` расширен до 200.
- [~] **Endless radio hardening follow-up (2026-05-07)**: добавлены Prometheus-метрики `radio_requests_total`, `radio_guard_hits_total`, `radio_queue_size` в `app/core/observability.py` + интеграция в `RecommendationService.get_radio` и `RadioService.build_queue`; добавлены unit-тесты `test_get_radio_guard_uses_last_queue` и `test_get_radio_cache_key_depends_on_exclude_ids` (прогон backend service-suite временно блокируется существующей SQLite DDL ошибкой `unrecognized token ":"` в test fixture setup).
- [x] **Endless radio phase-2 (2026-05-07)**: реализован A/B tuning радио через DB-настройку `recsys.radio_tuning` (варианты A/B, split по user bucket) с admin API `GET/PUT /api/v1/admin/system/radio-tuning`; tuning проброшен в PrivateCore (`RadioTuning`, `normalize_radio_tuning`, параметризованный `build_radio_queue`). Dashboard получил KPI-блок по радио через Prometheus (`radio_requests_5m`, `radio_guard_hits_5m`, `radio_queue_size_avg_5m`), плюс устранён SQLite test blocker (`genre_mix_overrides.track_ids server_default` без `::jsonb`) — backend service tests снова зелёные.
- [x] **Stats TODO close + i18n/typing batch (2026-05-07)**: TODO-пункт про отдельную страницу статистики артиста (`/artist/:id/stats`) закрыт как выполненный; в `RadioView` и `SearchView` убран оставшийся hardcoded text в пользу i18n-ключей, а в `frontend/src/lib/api.ts` ещё один пакет inline response-типов вынесен в именованные интерфейсы `frontend/src/types/api.ts` (`StatusResponse`, `OkResponse`, `MessageResponse`, `AuthConfigResponse`, `LinkStatusResponse`, `EqSettingsResponse`, `PrefetchPolicyResponse`, `ConversationRefResponse`, `SearchUserItem` и др.).
- [x] **i18n + API typings batch 2 (2026-05-07)**: `GenreMixView` очищен от `defaultValue`/RU fallback-строк в `t(...)` (чистые i18n-ключи), а в API-клиенте вынесены ещё inline-контракты в `frontend/src/types/api.ts` (`AdminManifestResponse`, `MyComplaintsResponse`, `UserPresenceResponse`, `ChatPresenceResponse`, `OnboardingGenrePreviewResponse`, `OnboardingArtistItem`, `SmartSkipResponse`, `RadioResponse`) с подключением в `frontend/src/lib/api.ts`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n + API typings batch 3 (2026-05-07)**: в `ProfileView` убраны fallback-строки у `t(...)` для вкладок/настроек (`profile.tabProfile`, `profile.tabImport`, `profile.tabComplaints`, `profile.openSettings`) и добавлены недостающие ключи в `frontend/src/locales/{ru,en}.json`; в `api.ts` закрыт оставшийся inline response для `getFollowedArtistsList` через новый `FollowedArtistListResponse` в `frontend/src/types/api.ts`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 4: LegalView localization (2026-05-07)**: `frontend/src/views/LegalView.tsx` полностью переведен на i18n-ключи без hardcoded RU текста (заголовки разделов, абзацы, пункты списков и подписи ссылок), добавлены ключи `redesign.legal.*` в `frontend/src/locales/i18n_extra2_{ru,en}.json`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 5: ChatView fallback cleanup (2026-05-07)**: в `frontend/src/views/ChatView.tsx` удалены все `defaultValue` и fallback-строки у `t(...)` (last-seen, saved-hint, block/unblock, empty/unread labels), оставлены только i18n-ключи `redesign.tracks.*`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 6: NowPlayingView fallback cleanup (2026-05-07)**: в `frontend/src/views/NowPlayingView.tsx` удалены fallback-строки из `t(...)` для player labels/aria/tabs/about (оставлены только `redesign.player.*` ключи); `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 7: TrackCard fallback cleanup (2026-05-07)**: в `frontend/src/components/TrackCard/TrackCard.tsx` удалены fallback-строки у `t(...)` в меню long-press (`like/unlike`, `addQueue`, `share`, `shareFail`, `longPressQueued`) — оставлены только i18n-ключи `redesign.tracks.*`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **Disable track downloading in Mini App (2026-05-07)**: из `TrackCardSheet` удалена кнопка «Скачать» и связанная offline-cache логика (`downloadTrack/isCached/removeTrack`), а из `LibraryView` убрана вкладка «Скачанные» (`offline` tab + i18n keys `library.tabOffline`); `npm run build` зелёный.
- [x] **Profile: вкладка дизлайков (2026-05-07)**: `GET /api/v1/dislikes/{user_id}` — только для авторизованного владельца (`403` если id не совпадает с `current_user`), пагинация и `source` как у лайков; репозиторий `list_disliked_tracks`, `DislikeService.list_disliked` + collapse вариантов; фронт: `DislikedView`, вкладка `profile.tabDislikes` в `ProfileView`, клиент `getDislikedTracks`, ключи `redesign.library.disliked*`; тесты `test_dislikes.py` / `test_dislike_service.py`.

## Платформы — будущее

- **Гибридный плеер**: для платформ с официальными embed-виджетами реализовать `access_mode="official_embed"` - храним embed URL, отрисовываем `<iframe>` вместо нативного плеера, отключаем EQ. Приоритет: YouTube (требует TOS раздел 5.D).
- **VK Музыка**: OAuth уже реализован (`linked_accounts`, scope `audio`). Нужно добавить `VKStreamService` (получает HLS-URL через `audio.getById` с user OAuth token) и расширить `playback.py`. Отложено - российский сервис.
- **Яндекс Музыка**: нужен новый OAuth-провайдер (`Yandex OAuth`, oauth.yandex.ru) + неофициальный API-адаптер. Отложено - российский сервис.
- **YouTube TOS compliance**: согласно TOS YouTube раздел 5.D прямой API-стриминг запрещен. Долгосрочно: мигрировать на `access_mode="official_embed"` (iframe-embed), API-стриминг оставить только как dev/fallback.

## Sprint concurrency hardening (2026-04-22)

- Backend: миграция `0045_dedupe_unique_constraints` - partial UNIQUE на `tracks.sc_url WHERE sc_url IS NOT NULL` и на `(imported_from, external_id) WHERE external_id IS NOT NULL`, `Index` объявлены в `app/models/track.py:Track.__table_args__` (создаются и для тестовой SQLite-схемы)
- Backend: `scripts/dedupe_tracks.py` - pre-migration helper, dry-run по умолчанию, мерджим дубли по `sc_url` и `(imported_from, external_id)` с union-find и FK-redirect для likes/dislikes/playlists/track_artists/ track_lyrics/track_info/track_upload_meta/complaints/listen_events/ comments/lyrics_jobs/search_events/messages
- Backend: `SoundCloudService.import_or_get_track` переписан на `INSERT ... ON CONFLICT (sc_url) WHERE sc_url IS NOT NULL DO NOTHING RETURNING` + fallback `SELECT`; `external_import_worker` обернут в `try/except IntegrityError` на случай rolldown-сценария
- Backend: миграция `0046_add_lyrics_sync_source_name` - `track_lyrics.sync_source_name VARCHAR(50) NULL`, проброс через `LyricsRepository.create_or_update`, `LyricsResponse` schema, `_result_to_payload(getattr(gen_result, "sync_source_name", None))`
- Backend: `app/services/sc_semaphore.py` - Redis-based counting semaphore (sorted-set + Lua acquire) вокруг SoundCloud `search`/ `resolve_url`/`get_stream_info`, env `SOUNDCLOUD_GLOBAL_CONCURRENCY=4`
- Backend: per-track Redis lock в `lyrics_worker.generate_lyrics_task` (рефакторинг через outer wrapper + `_generate_lyrics_task_impl`), env `LYRICS_PER_TRACK_LOCK_TTL_SECONDS=300`; race-protected через `SET NX EX` + Lua-release-on-match
- Backend: `app/services/import_queue_dispatcher.py` - backpressure через статус `"queued"`, env `IMPORT_MAX_CONCURRENT_JOBS=10`, `IMPORT_PER_USER_MAX_CONCURRENT=2`, dispatcher loop запускается в WORKER_STARTUP. `ImportService.start_import` возвращает job с `status="queued"` если глобальный или per-user cap занят; `get_queue_position` для UI; `cancel_job` и `_get_active_job` понимают `"queued"`
- Backend: `app/services/lyrics_global_orchestrator.py` - единый pacer через `BLPOP lyrics:queue:default`, фичерфлаг `LYRICS_GLOBAL_ORCHESTRATOR_ENABLED=true`, заменяет per-job пейсинг в `import_lyrics_worker.process_import_lyrics_task` (legacy mode сохранен, активируется выключением флага). Global circuit-breaker на 5 подряд `captcha|pool_exhaust|exhausted` сигналов из proxy_pool
- Backend: API `GET /import/{id}/status` и `/import/active` возвращают `queue_position` для queued джобов
- Backend: `main.py` зарегистрировал воркеры `app.services.import_queue_dispatcher` и `app.services.lyrics_global_orchestrator`
- Frontend: `ImportView.tsx` - новая фаза `"queued"` с отображением `queue_position`, polling переключается между `queued <-> importing` без пересоздания интервала
- Frontend: `LyricsPanel.tsx` и `FullscreenLyrics.tsx` - admin-only debug-блок «Источник текста» / «Синхронизовал» в самом конце отображенного текста, гейтится через `getIsAdmin()`; CSS `.lyrics-debug-attribution` (минимализм, монохром, monospace)
- Docs: `docs/private-core-dependency-policy.md` пополнен таблицей опциональных полей `GenerateResult` (включая новый `sync_source_name` - PrivateCore-side требуется добавить поле, Backend уже forward-compatible через `getattr`)
- Tests: `test_soundcloud_service::test_import_or_get_track_dedup_via_unique_index`, `test_lyrics_worker::test_sync_source_name_propagates_to_repo`, `test_lyrics_global_orchestrator.py` (новый файл, 7 тестов на serialize/deserialize/process_one), `test_import_service` (3 новых теста на backpressure + queue_position + cancel queued), `test_import_lyrics_worker` autouse-фисктура форсит legacy режим

## Sprint multi-importer library (2026-04-22)

- Backend: миграция `0047_add_user_track_library` - many-to-many таблица `user_track_library (user_id, track_id, source, imported_at)` с composite PK + индекс `(user_id, imported_at)`. Backfill из `tracks.uploaded_by_id` чтобы существующие треки попали в библиотеку владельца
- Backend: `app/models/user_track_library.py` (модель) + `app/repositories/user_track_library.py` (`add` идемпотентен через `INSERT ... ON CONFLICT DO NOTHING`, `list_by_user`, `count_by_user`, `has`, `remove`)
- Backend: auto-link во всех flow создания трека - `external_import_worker.py` (после `import_or_get_track`, включая dedup-resolved случай), `import_worker.py` (telegram), `upload_service.py` (UGC). Идемпотентно - повторный импорт одной песни одним юзером не дублирует
- Backend: `GET /api/v1/users/me/library` - paginated, ORDER BY `imported_at DESC`, `playable_only` filter; `TrackService.list_library`, `UserTrackLibraryRepository.list_by_user` с JOIN
- Backend: `LyricsService._get_editable_track` - для `catalog_type='external_reference'` редактирование лирики только админом, для UGC оригинальный uploader (как раньше). Все методы `create_or_update`/`update_sync`/`delete_lyrics`/`redefine`/ `trigger_auto_generation`/`cancel_auto_generation` переведены на новую проверку
- Backend: defensive `LyricsRepository.get_by_track_id` skip в `lyrics_global_orchestrator._process_one` - закрывает race window между `_enqueue_to_global_queue` и моментом обработки (другой воркер мог уже сохранить лирику)
- Frontend: `api.getMyLibrary(page, size, playableOnly)` метод; `ProfileView` переключен с `getMyTracks` на `getMyLibrary`, пользователь видит и свои аплоады, и импортированные треки
- Frontend: `LyricsPanel` принимает `catalogType` prop, кнопки редактирования гейтятся через `canEdit = isExternalRef ? isAdmin : isOwner`. Все 4 точки ownership-gating обновлены. `TrackCardSheet` пробрасывает `catalog_type`, edit-pane lyrics-toggle кнопка скрыта для non-admin на external_reference
- Frontend: `ImportView` фаза `done` показывает «Треки добавлены в вашу библиотеку (профиль)»
- Tests: `test_user_track_library.py` (7 кейсов: idempotency, shared-by-two-users, ordering, remove, count, has), `test_external_import_worker::test_two_users_share_track_with_two_library_links`, `test_lyrics_service` (3 новых: external blocks owner, allows admin, ugc owner ok), `test_lyrics_global_orchestrator::test_process_one_skips_when_lyrics_already_in_db`

## Sprint admin / auth (2026-04-19)

- Frontend: синхронный `api.restoreSession()` в `main.tsx` до рендера - убирает раннюю гонку токена с AdminProvider/PlayerProvider
- Frontend: `AdminContext.tsx` гейтит `getAdminManifest()` на наличие токена и подписан на `app-auth-ready` + `i18n.languageChanged`; убран orphan-импорт `adminBundleUrl`
- Frontend: `App.init()` пропускает `api.authTelegram('')` при пустом initData (убирает 422 + 500ms ретрай в ngrok-режиме)
- Frontend: `connectWS(...)` вызывается сразу в `verifyTelegramCode` / `verifyMagicLink` / `verify2FA`, плюс диспатч `app-auth-ready`
- Frontend: `restoreSession()` восстанавливает `auth-user-id` из JWT `sub`, если он потерян - убирает «при обновлении просит код»
- Frontend: Suspense fallback с timeout-ом и retry в `App.tsx` (`RouteFallback`) - убирает «черный экран» при зависших lazy-чанках
- Frontend: i18n RU/EN для всей админки (`admin.`* namespace в локалях, `useTranslation` в `AdminApp`, `AdminShell`, всех auth-формах и routes)
- Frontend: `AuthGate` запускает `ensureCsrf` и `bootstrapMetadata` параллельно через `Promise.allSettled` и пытается `adminApi.refresh()` на старте - admin-сессия переживает reload без TOTP
- Frontend: `useAdminAuth.capabilities` наполняется из манифеста после успешного refresh - `useCapability` теперь работает
- Frontend: proactive refresh за 30 сек до expiry в `adminFetch`; при фейле refresh статус `'needs_login'` вместо `'unauth'`
- Frontend: `AdminShell` - часы вынесены в изолированный `<Clock />`, остальная панель не перерисовывается каждую секунду
- Frontend: refetchInterval поднят до 15-30 сек и `refetchIntervalInBackground: false` во всех админ-routes (Dashboard, Logs, Tasks, Metrics, Containers, Security, Settings, AudioCompute)
- Frontend: удален orphan-файл `frontend/src/admin/AdminDashboardView.tsx`
- Frontend: `?nosw=1` в URL разрегистрирует service worker (отладка на ngrok)
- Frontend: убран дублирующий `<Route path="/admin">` без `*` в `App.tsx` - nested `<Routes>` в `AdminApp` теперь корректно рендерит `DashboardRoute`
- Frontend: `adminApi.refresh()` и `adminApi.logout()` больше не шлют `body: {}` - backend теперь читает refresh token из httpOnly-cookie без 422 от валидации `AdminRefreshRequest`

## Sprint bugfix (2026-04-20)

- **(0)** Policy amendment: расширить "Source Attribution Exception" на lyrics / track-info провайдеров (`CLAUDE.md` + `docs/ai-boundary-policy.md`)
- **(1)** Track info: перенос из внешней кнопки внутрь `TrackCardSheet` (после блока «похожие треки»), DEBUG-refresh (admin), автозагрузка и polling
- **(2)** Track info worker: `/api/v1/tracks/{id}/info` зависает в `fetching` - stale-retry в сервисе, `asyncio.wait_for` timeout 90s в воркере, `fetched_at` отражает последнее состояние
- **(3)** `TrackCardSheet`: белая заливка прогресс-бара - CSS gradient с `--progress` + inline style на seek-input
- **(4)** `SettingsSheet`: кнопка «Назад» с label + Telegram BackButton + Esc
- **(5)** `TrackCardSheet`: крестик 44х44, safe-area-inset-top/right, не выходит за рамки
- **(6)** `TrackCardSheet`: «Перейти к автору» использует `track.artist` через `onOpenArtist`; ряд загрузчика переименован
- **(7)** Admin: `/logs/query` и `/metrics/range` возвращают `source_status` + `/system/observability` endpoint, banner в `LogsRoute` / `MetricsRoute`
- **(8)** Admin lyrics-jobs: индивидуальный cancel (inline-кнопка) + bulk `POST /tasks/lyrics-jobs/cancel-queued`; `queued` сразу переводится в `cancelled` в БД
- **(9)** Admin Artists: `DELETE /artists/{id}`, клик по имени - `/mini_app/artist/:id` (новая вкладка), fix даты через fallback на `created_at`, `updated_at` добавлен в `ArtistResponse`
- **(10)** Admin Tracks: existing `DELETE` + visibility-toggle + inline `<audio>` + открытие `/mini_app/track/:id`
- **(11)** Admin Users: ban/unban + `POST /users-ext/{id}/force-logout` (revoke admin sessions + Redis marker) + `POST /users-ext/{id}/message` (DM через `ChatService`/`MessageService`)
- **(12)** Lyrics: cache-hit с text-only при `with_sync=true` пре-сохраняет текст в БД и продолжает в audio-based sync flow
- **(13)** WS: `_is_ws_open()` guard + `try/except (WebSocketDisconnect, RuntimeError)` - ранний выход из `_broadcast_loop`
- **(14)** Lyrics: `LyricsResponse.source_name` (optional) для UI-attribution + `lyrics_provider_name` / `track_info_provider_name` env-flag selectors; алгоритмика остается в PrivateCore

## Playback variants / composition grouping (2026-04-29)

- `[x]` PrivateCore: `playback_variant_policy` (порядок платформ, tolerance)
- `[x]` Backend: `composition_group_id`, `PlaybackVariantService`, `build_track_response` / `dedupe_and_build_track_list`, `TrackResponse.playback_variants`, лайки/дизлайки по группе, комментарии по `variant_ids`, read-only stream fallback
- `[x]` Frontend: типы API, `LikesContext` по `playback_variant_track_ids`, переключатель источника в плеере
- `[x]` Tests: mock `catalog_only_lyrics_task.kiq` в `create_test_track` / `mock_taskiq` и в `test_upload_track_success`
- `[x]` `scripts/backfill_composition_groups.py` (stub)

## Home Menu Redesign - v2 (2026-05-04)

- `[x]` **ArtistFollowRepository**: `list_followed_artists(user_id, limit)` - `list[Artist]`
- `[x]` **Schemas**: `FollowedArtistItem`, `FollowedArtistListResponse` в `artist_follow.py`
- `[x]` **API**: `GET /api/v1/artists/followed` endpoint
- `[x]` **PrivateCore**: `build_genre_mixes()`, `GenreMixResult`, `MAX_GENRE_MIXES`, `GENRE_MIX_SIZE` в `recommendation_engine.py`; экспорт в `services/__init__.py`
- `[x]` **Backend**: `GET /api/v1/recommendations/genre-mixes` (endpoint + `RecommendationService.get_genre_mixes()`)
- `[x]` **Backend**: `GET /api/v1/recommendations/radio` - добавлен `exclude_ids` query param (max 30)
- `[x]` **RecommendationService.get_radio**: принимает `exclude_ids: list[int] | None`
- `[x]` **Schemas**: `GenreMixItemResponse`, `GenreMixesResponse` в `recommendation.py`
- `[x]` **global.css**: все Home v2 CSS-классы (greeting, quick-grid, carousel, artist-strip, genre-mix-card, player-radio-badge, top nav-indicator)
- `[x]` **api.ts**: `getFollowedArtistsList()`, `getGenreMixes()`, обновлен `getRadio(excludeIds?)`
- `[x]` **types/api.ts**: `FollowedArtistItem`, `GenreMixItem`, `GenreMixesResponse`
- `[x]` **HomeView.tsx**: полный редизайн - приветствие, quick-grid, genre mixes carousel, followed artists strip, секционные карусели треков по section_type
- `[x]` **BottomNav.tsx**: верхний индикатор (`.nav-btn__indicator`) для активного таба
- `[x]` **GenreMixView.tsx**: новый view `/genre-mix/:genre`
- `[x]` **App.tsx**: маршруты `/genre-mix/:genre`; lazy-import `GenreMixView`
- `[x]` **Icon.tsx**: добавлены иконки `radio`, `users-following`
- `[x]` **PlayerContext.tsx**: `radioMode`, `radioSeedTrackId`, `startRadio()`, `stopRadio()`; `playNext()` - авто-fetch при пустой очереди в radio-режиме; `played_ids Set` (max 50)
- `[x]` **RadioView.tsx**: переработан - кнопка «Запустить бесконечное радио», индикатор режима, история прослушивания
- `[x]` **PlayerBar.tsx**: `.player-radio-badge` при активном `radioMode`; клик - `/radio`
## Chats / Track Share (2026-05-04)

- [x] Share track to chat ? modal picker in TrackCardSheet, send via api.sendMessage(..., { type: 'track_share', shared_track_id }), and shared-track bubble with Play in ChatBubble.
- [x] Chat share: albums and playlists (shared_album_id, shared_playlist_id) + updated Home track/artist card styling for .sound consistency (2026-05-04).

## Lyrics Roadmap

- [x] Add support for per-track lyrics translations (store translated text separately from original lyrics), including backend API/model + minimal language switch in lyrics UI (2026-05-06).
- [x] RU/EN brand switch for mini app: default '.звук', English '.sound' (loader, splash, auth, home, admin shell, static build sync) - 2026-05-04

---

## Future Features & Enhancements (Planned May 2026)

- [ ] **AI-Mood & Genre Tagging (v1)**
    - [ ] Автоматическое тегирование на основе анализа аудио (ComputeWorker).
    - [ ] Анализ метаданных и текста песен через LLM (определение настроения/жанра).
    - [ ] Хранение в Backend и отображение в UI.
- [ ] **Listening Party (v2)**
    - [ ] Интеграция с чатами (создание комнат внутри групп).
    - [ ] "Демократичная очередь" (голосование за треки).
    - [ ] Улучшение UI и синхронизации.
- [ ] **Музыкальные профили и статистика**
    - [ ] Карточки "Топ артистов/треков" месяца для шеринга.
    - [ ] Детальная статистика в профиле (часы прослушивания, любимые жанры).
    - [ ] Секция "Ваш топ" на главной.
- [ ] **Динамические плейлисты**
    - [x] "Weekly Top 50" -- 2026-05-06: PrivateCore weekly_top_policy (rank_weekly_top_tracks, blend log(listens_7d)+log(likes_7d), WEEKLY_TOP_SCORE_VERSION); Backend RecommendationRepository.get_qualified_listens_7d_counts, RecommendationService.get_weekly_top_playlist with Redis cache (TTL 30 min), GET /api/v1/recommendations/weekly-top; Frontend WeeklyTopView (/weekly-top), api.getWeeklyTopPlaylist, WeeklyTopPlaylistResponse type, flame icon, Home quick-grid card.
    - [x] **«Забытые сокровища»** (лайкнутое давно, без прослушиваний в окне) — PrivateCore `forgotten_treasures_policy` (пороги лайка ≥21d, тишина ≥14d, `rank_forgotten_treasure_tracks`); Backend `RecommendationRepository.list_forgotten_treasure_rows`, `GET /api/v1/recommendations/forgotten-treasures` (JWT, per-user); Mini App `ForgottenTreasuresView` `/forgotten-treasures`, тайл в быстрых разделах после «Выбор»; prefetch context `forgotten_treasures`.
- [ ] **PWA Offline Mode (v2) [High Priority]**
    - [ ] Кеширование HLS чанков в Service Worker.
    - [ ] Надежный UI для оффлайн-режима.
- [ ] **Anti-Abuse Fingerprinting**
    - [ ] Перенос логики в PrivateCore.
    - [ ] Анализ поведения для борьбы с накрутками.


- [x] Public UI: admin inline editing for playlists/albums/tracks via non-admin routes with backend admin checks + reorder endpoints (2026-05-05).
- [x] Frontend: fixed share copy toast layering above share modal for track/album/playlist (z-index via --z-toast, 2026-05-05).
- [x] Frontend: TrackCardSheet now resolves album edit/share via fallback track.album_id (for mixes/playlists where card.album may be empty), 2026-05-05.
- [x] Frontend: share copy toasts can render at top (position=top) to avoid overlap with share modal; admin flag fallback from JWT claim is_admin in getIsAdmin, 2026-05-05.
- [x] Frontend: Apple-like .звук splash typography + loading animation; edit UI gates in TrackCardSheet simplified to admin/debug/dev for mix album editing on Home, 2026-05-05.
- [x] Frontend: ArtistView now shows a prominent monthly unique listeners KPI card in artist header (always visible with API fallback), 2026-05-05.
- [x] Frontend: ArtistView monthly listeners moved to compact inline text under artist avatar/name with new `users-listeners` SVG icon, 2026-05-05.
- [x] Frontend: Home greeting now shows only day/evening format (`Добрый день|вечер`) with optional user name (`| {{name}}`) and fallback without name, 2026-05-05.
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

- [x] **Stage H (recap / achievements)** — 2026-05-07: `RecapStoryStage` (9 слайдов, auto-advance, long-press pause, tap-зоны), `RecapView` + `/recap?tab=achievements` → `AchievementsView`, share sheet + `RecapShareCard` (9:16, TODO на реальный export без новых npm), `redesign-recap.css`, `getRecapSnapshotMock()` + `redesign.recap.*` в `i18n_extra2_*`.
- [~] **Stage D (library): поиск, медиатека, лайки, плейлисты** — 2026-05-07: `redesign-library.css`, `SearchView` (чипы фильтра сущностей, motion), `LibraryView` (tabs + layoutId, daily mix `MotionPress`), `LikedView` (сортировка, чипы `MotionPress`, sticky-шапка), `PlaylistsView` (сетка, `LongPressMenu`, поток «поделиться» с экрана списка), ключи `redesign.library.*` в `i18n_extra2_*.json`. Дальше: polish профиль/настройки, Stage F (artist shell), отдельные коммиты после `tsc`/`build`.

- [x] **Cross-cutting motion polish (batch 3)** — 2026-05-07: финальный проход MotionPress/MorphIcon по
  `AchievementsView` (плитки достижений), `Notifications/NotificationBell` + `NotificationList` (колокольчик,
  пункты меню, кнопки строк, more-vertical, close), все Import-модалки (`PlatformImportMethodModal`,
  `SoundCloudPlaylistUrlModal`, `VkMusicUrlModal`, `SpotifyUrlModal`, `YandexMusicUrlModal`) и `ImportView`
  (selectAll/deselectAll/cancel, queued/importing/done, cancel-confirm dialog), `Chat/VoiceRecorder` +
  `VoicePlayer` (cancel/play/preview/send + waveform speed), `Settings/AccountDangerZone` и
  `Settings/OAuthImportAccounts`. Inline-стили `style={{padding,gap,flex,...}}` вынесены в новые классы
  `rf-import-*`, `settings-danger-zone__*`, `settings-badge--clickable` (`redesign-artist.css`, `global.css`).
  TS clean (`npx tsc --noEmit`), `npm run build` зелёный, hygiene + admin-bundle проверки прошли.

- [x] **Micro-polish pass (batch 4)** — 2026-05-07: `OnboardingImportStep` полностью переведён с plain `<button>`
  на `MotionPress` (карточки источников, CTA в `empty/done/select/queued/importing`, оба confirm-модала), inline
  стили заменены классами `onboarding-import-*` в `global.css`; в `admin/routes/DashboardRoute` tick-кнопки
  metric slider также переведены на `MotionPress` (`icon` + `selection`). Проверки: `npx tsc --noEmit`, `npm run build`.

## Session Updates (2026-05-08)

- [x] Исправлены битые UTF-8 последовательности и восстановлены русские строки в `TODO.md`
  (блок Mini App UI, backlog «Home recommendations», секция «Платформы — будущее»);
  у пункта «Frontend: отдельная страница статистики» унифицирован формат статуса `[x]` (без лишних backticks).

- [x] Динамический плейлист **«Забытые сокровища»**: PrivateCore `forgotten_treasures_policy`, Backend
  `GET /api/v1/recommendations/forgotten-treasures`, Mini App `/forgotten-treasures` + prefetch context
  `forgotten_treasures`; pytest (PrivateCore ranking + API), `npm run build` зелёный.
