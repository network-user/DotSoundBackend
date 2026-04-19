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

## Критичные / Инфраструктура

- [x] Система бэкапов: PostgreSQL + Redis + configs (локально)
- [x] Система логирования: JSON structlog + Docker log rotation
- [ ] **Полное копирование аудиофайлов (MinIO) на удалённый backup-VPS**
  - Подключение к отдельному серверу по SSH
  - `mc mirror` MinIO -> remote, инкрементально
  - Шифрование трафика, ключевая аутентификация
  - Настройка через `.env` (`BACKUP_REMOTE_HOST`)
  - UI в админ-панели: запуск/статус/расписание бэкапа
- [ ] Админ-панель (frontend): раздел управления бэкапами
  - Просмотр списка бэкапов, размеры, даты
  - Ручной запуск полного бэкапа
  - Настройка расписания
  - Статус последнего бэкапа (OK / FAIL)
  - Кнопка восстановления (с подтверждением)

## Админ-панель (выполнено)

- [x] **Полноценная админ-панель** (Phase 1-5)
  - [x] Backend `/api/v1/admin/*`: auth (TOTP onboarding с QR, login,
    device approval, step-up, refresh, logout), dashboard,
    tracks/users/complaints (без inline SQL), tasks (lyrics_jobs +
    Taskiq queues + worker audit), logs (Loki proxy), metrics
    (Prometheus proxy), system (services health, containers,
    migrations, feature flags на app_settings), audit
    (admin_actions_log + CSV export), security (login attempts,
    locked users, lockout release), WebSocket для realtime
  - [x] Многоуровневая защита: admin TOTP + device binding +
    pending_device email-flow + step-up для критичных действий +
    Telegram-алерты + короткие 15-мин сессии + rotating refresh +
    CSRF double-submit + строгий CSP + brute-force lockout
  - [x] Observability: Prometheus + Grafana + Loki + Tempo +
    cAdvisor через `docker-compose.observability.yml`,
    `app/core/observability.py` (metrics/tracing/Sentry с PII-фильтром),
    расширенный `/health/deep` (db/redis/s3/taskiq/loki/prometheus)
  - [x] Frontend `frontend/src/admin/` как chunked secure bundle:
    AdminApp, routes, layout, recharts графики, TanStack
    Query/Table, Zustand stores, semantic state-tokens только
    для StatusPill (см. design-system.md)
  - [x] Документация: `docs/admin/{README,security,onboarding,testing,nginx-example.conf}`
- [ ] Перенести admin-security policy в PrivateCore (см. выше)
- [ ] WebAuthn/Passkey как опциональный второй фактор

## Безопасность

- [x] Scoped JWT для internal-token (bot_player, 15 мин TTL)
- [x] IP whitelist + rate limit на internal endpoints
- [x] hmac.compare_digest для secret comparison
- [x] Аудио sanitization через FFmpeg перекодирование (payload уничтожается)
- [ ] Аудит-лог входов через бота (расширить login_history)
- [ ] Rate limit тюнинг под production нагрузку
- [x] **Глубокая валидация загрузок (Layer 1)**
  - `python-magic-bin` для проверки magic bytes (`file_validator.py`)
  - Интеграция в audio upload, cover upload, video upload
  - Запрет двойных расширений (`.exe`, `.bat`, `.cmd` и др.)
- [x] **Sanitization изображений (Layer 2)**
  - Pillow re-encode для обложек и аватаров (через `media_service.process_image`)
- [~] **Сканирование загрузок: режим `lightweight` ИЛИ `clamav`**
  - [x] Конфиг `upload_malware_scan_mode: none | lightweight | clamav` в `config.py`
  - [x] `scan_service.py` stub (ScanResult, scan_bytes)
  - [x] Документировано в `.env.example` с рекомендациями по VPS
  - [ ] Реализация `lightweight` режима (YARA + эвристики, PrivateCore)
  - [ ] Реализация `clamav` режима (clamd TCP/socket, quarantine flow)
  - [ ] Разделить слои: сигнатуры/эвристики/пороги в PrivateCore, clamd/quarantine orchestration в Backend
- [x] **CSP и изоляция (Layer 4)**
  - `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff` на все ответы
  - `Content-Security-Policy: default-src 'none'` на медиа-ответы

## Граница Backend / PrivateCore

- [x] **Immediate: перенести auth/email policy в PrivateCore**
  - [x] `account_linking_service`: `_LINK_TTL`, `_LINK_EMAIL_TYPE`, `_LINK_PREFIX`, `_LINK_TG_PREFIX`
  - [x] `account_linking_service`: импортировать `is_disposable_email` из `dotsound_private_core.services.abuse`
  - [x] `email_auth_service`: `_2FA_SESSION_TTL`, `_MAGIC_LINK_TYPE`, `_2FA_SESSION_TYPE`, `_ML_PREFIX`
  - [x] `email_auth_service`: policy генерации fallback OTP (6-значный код) перенести в helper PrivateCore
  - [x] `email_sender`: текст TTL fallback-кода строить от `FALLBACK_CODE_TTL`, без hardcoded `5 minutes`
- [x] **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - [x] Перенесён inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - [x] `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` доступны через `AdminRepository`/admin endpoints
- [x] **Перенести admin-security policy в PrivateCore**
  - [x] Создан `dotsound_private_core/services/admin_security_policy.py`
    с константами и decision-функциями
  - [x] Удалён временный stub `app/core/_admin_security_constants.py`
  - [x] Все backend модули (admin_auth_service, admin_device_service,
    admin_alert_service, admin_manifest_service, ws.py, observability.py)
    переключены на импорт из PrivateCore
  - [x] Добавлен endpoint-контракт `ADMIN_ALERT_ENDPOINT` в
    `dotsound_private_core/contracts/internal_api.py` + URL builder
    `admin_alert_url` в `internal_bridge.py`
  - [x] Реализован `handle_admin_alert` в DotSoundBot
    (`bot/api/internal.py`) с allowlist `chat_id` и HTML-escape
  - [x] Тесты: PrivateCore 88 admin-related, Bot 9 admin alert,
    Backend smoke + repo

## Плеер в боте

- [x] Inline аудио-плеер (3 трека, editMessageMedia)
- [x] Выбор источника: Мои / Лайки / Лента
- [x] file_id кэш в Redis
- [x] Предзагрузка следующей пачки
- [x] Фильтрация треков без файлов (playable_only)
- [ ] Расширить источники: плейлисты, подписки, рекомендации
  - Для источника "рекомендации": алгоритм ранжирования и скоринг в PrivateCore, Backend/бот — адаптеры выдачи
- [ ] Shuffle / Random режим

## Интернационализация (i18n)

- [x] **Английская версия сайта (базовая)**
  - `react-i18next` + `i18next-browser-languagedetector`
  - JSON-каталоги `ru.json` / `en.json` (ключевые экраны: Auth, Home, Nav, Search, Liked, Upload, Profile, Playlists, Settings)
  - Telegram `language_code` custom detector
  - Переключатель языка в SettingsSheet
  - Поле `locale` в модели User + PATCH /users/me
  - Alembic миграция `0024`
- [ ] i18n: мигрировать оставшиеся ~35 .tsx файлов на `useTranslation`

## Эквалайзер

- [x] 8-полосный Web Audio EQ (32 Hz -- 16 kHz)
- [x] Preset-система
- [x] Серверная синхронизация настроек (`GET/PUT /api/v1/users/me/eq`)
- [ ] **Улучшения эквалайзера (v2)**
  - Параметрический Q-factor (ширина полосы) на каждой полосе
  - Визуализация АЧХ в реальном времени (canvas/SVG)
  - Дополнительные пресеты: Bass Boost, Vocal, Classical, Electronic
- [ ] **Продвинутая обработка (v3)**
  - Compressor/Limiter (`DynamicsCompressorNode`)
  - Stereo Balance / Pan
  - Loudness normalization

## PWA / Фоновый плеер

- [x] Media Session API (lock-screen контроли: play/pause/next/prev/seekto)
- [x] Браузерная версия с email auth + Telegram code auth
- [x] **PWA-слой поверх текущего SPA**
  - `manifest.json` через `vite-plugin-pwa` (name, icons SVG, standalone, theme_color)
  - Service Worker: `NetworkFirst` для API, `CacheFirst` для статики
  - Иконки: 192x192 и 512x512 SVG в `frontend/public/`
  - Meta-теги: theme-color, apple-touch-icon, apple-mobile-web-app-capable
- [ ] Picture-in-Picture для видео-треков
  - `video.requestPictureInPicture()` в `TrackCardSheet.tsx`
- [ ] **Offline-кэш треков (сохранение для оффлайн-прослушивания)**
  - **Сохранение**: кнопка "Скачать" на TrackCardSheet; аудио кешируется в Cache API (`caches.open('offline-tracks')`)
  - **Хранилище**: IndexedDB для метаданных (track JSON, обложка blob, статус); Cache API для аудиофайлов
  - **Управление**: экран "Скачанные" (список, занято места, кнопка удаления); лимит по объёму (настраиваемый, ~500MB)
  - **Оффлайн-режим**: Service Worker перехватывает `/api/v1/tracks/{id}/audio` и `/hls/` — если есть в кеше, отдаёт локально
  - **Плеер**: `playTrack()` проверяет Cache API перед сетевым запросом; оффлайн-треки играют без интернета
  - **Синхронизация**: при появлении сети — sync play counts (Background Sync API); обновление метаданных
  - **Ограничения**: HLS-треки кешировать как один файл через fallback endpoint `/audio`; DRM/лицензирование не применяется (UGC-платформа)
- [ ] **Грамотный единый плеер для разных платформ / источников**
  - Привести к единому UX `ugc`, `licensed`, `external_reference`
  - Разделить `access_mode`: `internal_stream`, `third_party_stream`, `official_embed`, `external_link`
  - Показать пользователю понятный режим доступа: наш стрим / внешний поток / открыть источник
  - Для каждого источника определить допустимую механику playback и ограничения по Terms
  - Гармонизировать `PlayerContext`, `TrackCard`, `TrackCardSheet`, deep links и search/import UX
  - Не смешивать в UI внешний reference и внутренний storage-backed трек как один и тот же тип воспроизведения

## Видео к трекам

- [x] Загрузка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- [x] Удаление видео (`DELETE /tracks/{id}/video`)
- [x] Отдача видео (`GET /tracks/{id}/video`, proxy из S3)
- [x] UI: фоновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- [x] **Оптимизация/сжатие видео**
  - Taskiq task `transcode_video` (`video_transcoding.py`): FFmpeg H.264 + AAC
  - Max 720p, CRF 23, `-preset medium`, `-movflags +faststart`
  - Thumbnail генерация (FFmpeg `-ss 1 -frames:v 1`)
  - `video_processing_status` + `video_thumbnail_key` на Track (миграция `0023`)
  - Upload -> temp S3 -> queue -> async transcode -> update status
- [x] Увеличить лимит загрузки до 50MB (из PrivateCore `MAX_VIDEO_BYTES`)
- [ ] Адаптивный HLS для видео (как для аудио)
- [ ] Ограничение длительности видео (Canvas-стиль или длина трека)
- [ ] Учёт видео в storage quota пользователя

## Метаданные трека

- [x] Изменение `is_public` после загрузки (PATCH)
- [x] Загрузка/замена обложки
- [x] Загрузка/удаление видео
- [x] Текст песни (plain text) + синхронизированные тайм-коды
- [x] **Редактирование title, artist, genre после загрузки**
  - `TrackUpdateRequest` расширен (Optional поля title/artist/genre/description)
  - `TrackRepository.update_track()` + `TrackService.update_track()`
  - PATCH endpoint обновлён: принимает любую комбинацию полей
- [x] Поле `description` в модели Track (TEXT, nullable)
  - Alembic миграция `651109411149`
- [x] **Автоопределение текста песен (lyrics auto-detection)**
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
  - [x] Re-define fix: админ-кнопки с `bypass_cache=true` + расширенные debug-логи в карточке (шестерёнка)
  - [x] Search fallback fix: при miss по `(artist,title)` делаем retry по `title-only` и сохраняем cache alias
- [ ] **Auto-lyrics: вынос тяжёлой обработки на внешний GPU-сервис (далёкое будущее)**
  - Отдельный сервер/сервис с GPU для обработки аудио
  - Backend отправляет аудиофайл во внутренний API PrivateCore,
    а PrivateCore уже сам решает, обрабатывать локально или вызывать внешний GPU-сервис
  - Интеграция через существующий `lyrics_provider` в PrivateCore (внешние детали — внутри чёрного ящика)
- [ ] Теги (`tags`, JSONB или отдельная таблица)
- [ ] BPM auto-detection (background task, `librosa` / `essentia`)
  - Извлечение фич/пороги confidence и decision rules в PrivateCore, Taskiq orchestration и запись результата — в Backend
- [ ] Waveform generation (pre-render формы волны для UI)

## Чат и комментарии

- [x] Чат: DM, группы, WebSocket real-time
- [x] Реакции, вложения, голосовые сообщения, шифрование
- [x] WebSocket: Redis pub/sub, presence, typing indicators
- [x] Комментарии к трекам: CRUD, голосование, пин, скрытие
- [~] Доработки чата (обсудить отдельно)

## Карточка артиста (multi-source)

- [x] Policy-exception для явного source attribution
  (`source_name` + `source_page_url`) зафиксирован в
  `docs/ai-boundary-policy.md` (Backend + PrivateCore)
- [x] PrivateCore: расширен контракт `ArtistInfo` полями
  `source_profiles`, `primary_source_id`, `discography`
- [x] Backend: добавлены `artists.source_profiles` (JSON) и
  `artists.primary_source_id` (миграция `0039`)
- [x] Backend API: `ArtistDetailResponse` и `/api/v1/artists/{id}`
  возвращают `source_profiles` и `primary_source_id`
- [x] Frontend ArtistView: горизонтальный переключатель источников
  под аватаром + рендер bio/meta/discography по выбранному источнику
- [x] Frontend ArtistView: полноэкранный просмотр аватарки с
  закрытием по overlay / кнопке / `Esc`
- [x] Frontend ArtistView: отдельная строка
  `Источник: <source_name>` с кликабельной ссылкой на страницу
  источника
- [x] Регрессионные тесты обновлены:
  - PrivateCore `test_artist_info_provider.py`
  - Backend `test_artist_enrichment_service.py`,
    `test_artist_enrich.py`, `test_artist.py`

## Предзагрузка треков

- [x] Предзагрузка следующей пачки в боте (DotSoundBot)
- [x] `GET /tracks/{id}/adjacent` (sequential/shuffle/repeat_one)
- [x] hls.js с ABR (`startLevel: -1`, `enableWorker: true`)
- [x] **Prefetch в Mini App / браузере (метаданные)**
  - `GET /tracks/{id}/queue?count=3` -- новый endpoint
  - `TrackRepository.get_next_tracks()` возвращает N следующих треков
  - Кеш в `PlayerContext` через `useRef` (`prefetchCacheRef`)
  - `playNext` использует кеш, fallback на `getAdjacentTracks`
- [ ] **Предзагрузка аудио следующего трека (gapless)**
  - При проигрывании текущего трека — начинать буферизацию аудио следующего трека в фоне
  - Скрытый `<audio>` элемент (`preloadAudioRef`) с `preload="auto"` загружает URL следующего трека
  - Для HLS: создать второй `Hls` instance, привязать к preload-элементу, дождаться `MANIFEST_PARSED`
  - При `playNext` — swap: preload-элемент становится основным, мгновенный старт без буферизации
  - Запуск предзагрузки по порогу (например, текущий трек проигран на 75% или осталось < 30 сек)
  - Отмена предзагрузки при ручном переключении на другой трек
  - Ограничение: предзагружать только 1 следующий трек (экономия трафика)

## Идентификация загрузчика

- [x] `uploaded_by_id` на Track (FK -> User с telegram_id)
- [x] `created_at` / `updated_at` timestamps
- [x] `RequestLoggingMiddleware` логирует `client_ip` в structlog
- [x] **Расширенные метаданные загрузки (admin-only)**
  - Модель `TrackUploadMeta` (миграция `0022`): `upload_ip`, `upload_user_agent`, `upload_telegram_data` (JSON)
  - Заполнение при upload из `request.client.host` + headers
  - Admin endpoint `GET /admin/tracks/{id}/upload-meta`
  - PrivateCore: `UPLOAD_META_RETENTION_DAYS = 90`
- [ ] Taskiq job для автоудаления meta старше retention (GDPR)

## Удаление аккаунта

- [x] **Soft delete с grace period (30 дней)**
  - `DELETE /api/v1/users/me` (body: `{"confirmation": "DELETE"}`)
  - `POST /api/v1/users/me/restore` -- восстановление в grace period
  - `deleted_at` на User (миграция `0021`)
  - PrivateCore: `account_deletion_policy.py` (GRACE_PERIOD_DAYS, is_within_grace_period, is_valid_confirmation)
  - Auth flow: soft-deleted пользователи в grace period проходят auth
- [ ] Taskiq job для hard delete после 30 дней
- [ ] **Политика удаления данных**
  - Профиль, аватар, настройки EQ -- удалить
  - Лайки, дизлайки, подписки -- удалить
  - Сообщения в чатах -- анонимизировать ("Deleted User")
  - Комментарии -- анонимизировать
  - Плейлисты -- удалить
  - Треки -- выбор пользователя: удалить или оставить анонимно
  - S3 объекты -- удалить при удалении трека
- [ ] **Подтверждение удаления**
  - Повторная авторизация
  - Текстовое подтверждение ("DELETE")
  - Email/Telegram уведомление
  - Политику re-auth/cooldown/max-attempts для удаления хранить в PrivateCore

## Frontend / Mini App

- [x] Восстановление позиции воспроизведения при перезапуске
- [x] Монохром-фильтр в настройках
- [ ] Админ-панель: управление пользователями
  - Если добавятся баны/risk flags/anti-abuse actions, decision rules и пороги должны идти из PrivateCore
- [ ] Админ-панель: модерация контента
  - Пороги auto-hide/escalation и moderation policy держать в PrivateCore, панель — UI + вызовы Backend API
- [ ] Админ-панель: управление бэкапами (см. выше)

## Frontend оптимизация

- [x] **PlayerContext split (производительность)**
  - 3 контекста: `PlayerStateCtx` (currentTime, duration, isPlaying),
    `PlayerActionsCtx` (стабильные callbacks через useCallback),
    `PlayerMetaCtx` (track, volume, EQ, модалки)
  - 3 хука: `usePlayerState()`, `usePlayerActions()`, `usePlayerMeta()`
  - `usePlayer()` -- compat shim для плавной миграции
- [x] **LikesContext оптимизация**
  - `useMemo` на value, `useCallback` на все функции
- [x] **React Router (deep links, PWA)**
  - `react-router-dom` v7 (React Router)
  - Маршруты: `/`, `/search`, `/upload`, `/liked`, `/playlists`,
    `/chats`, `/chats/:id`, `/profile`, `/track/:trackId`
  - `BottomNav` через `useNavigate` + `useLocation`
  - `BrowserRouter basename="/mini_app"`
  - Browser back/forward, shareable URLs, deep links
- [x] **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView, LikedView, PlaylistsView, ChatsView, ProfileView
  - `hls.js` в отдельный chunk (`manualChunks`)
  - `<Suspense>` обёртка для route-level lazy loading
- [ ] **TanStack Query (API кеширование)**
  - Автоматический кеш, дедупликация, stale-while-revalidate
  - Постепенное внедрение (endpoint за endpoint)
- [x] Типизация: убрать 5x `Promise<any>` в `api.ts`
  - `ImportJobResponse` + `ImportAudioInfo` в `types/api.ts`
  - `genre` + `description` добавлены в `Track` interface
- [ ] CSS: рассмотреть разделение `global.css` (~2700 строк)

## Backend API

- [x] playable_only фильтр в track listing endpoints
- [x] internal-token endpoint с полной защитой
- [ ] WebSocket: событие player.state для синхронизации
- [x] Пагинация liked tracks (backend + frontend)
  - Backend: `page`/`has_more` в `UserLikesResponse`
  - Frontend: `LikedView` с "Показать ещё" кнопкой

## Юридический аудит: анализ конкурентов (UGC + ст. 1253.1)

> **Цель**: изучить каждый сервис из списка на 2 вещи:
> 1. Наличие web-плеера / API для стриминга — возможна ли ретрансляция
>    аудио на DotSound (аналогично SoundCloud: звук передаётся
>    пользователю, плеер наш, мы оболочка).
> 2. Политика, соглашения, правовая реализация — что можно
>    адаптировать для DotSound (тексты оферт, дисклеймеры,
>    процедуры takedown, формы загрузки с подтверждением прав).

### Категория 1: Прямые аналоги (UGC + информационный посредник)

- [ ] **Musify.club**
  - Web-плеер: есть ли публичный стрим/API, можно ли встроить
  - Юридика: пользовательское соглашение (ст. 1253.1), страница
    `/contacts/legal` (перечень лицензий с ООО «АдвМьюзик» и др.),
    процедура DMCA/takedown, форма загрузки
  - Выводы: что адаптировать для DotSound
- [ ] **4beat.ru**
  - Web-плеер: стрим, embed, API
  - Юридика: пользовательское соглашение, форма загрузки трека
    (какие галочки/подтверждения прав требуют), страница правообладателям
  - Выводы: что адаптировать для DotSound
- [ ] **QPlet.ru**
  - Web-плеер: стрим, публичный доступ к аудио
  - Юридика: условия загрузки, онбординг артиста, оферта
  - Выводы: что адаптировать для DotSound
- [ ] **Созвук (sozvuk.ru)**
  - Web-плеер: стрим, embed, API для треков
  - Юридика: публичная оферта (ст. 1253.1), как оформлены права
    при загрузке, политика удаления по жалобе
  - Выводы: что адаптировать для DotSound

### Категория 2: Крупные платформы с UGC-компонентом

- [ ] **VK Музыка (vk.com/music)**
  - Web-плеер: закрытый API, возможность ретрансляции
  - Юридика: лицензионное соглашение (`vk.com/terms/music`),
    Content ID, как разделяют лицензированный и UGC-контент,
    процедура жалоб
  - Выводы: что адаптировать для DotSound
- [ ] **Яндекс.Музыка**
  - Web-плеер: закрытый стрим, ранжирование UGC vs лицензированное
  - Юридика: условия загрузки пользовательской музыки,
    как UGC показывается ниже официального в поиске
  - Выводы: что адаптировать для DotSound
- [ ] **ZVUK (zvuk.com)**
  - Web-плеер: стрим, партнёрская модель
  - Юридика: условия для артистов, договоры с дистрибьюторами,
    требования к правам
  - Выводы: что адаптировать для DotSound

### Категория 3: Серая зона

- [ ] **Зайцев.НЕТ (zaycev.net)**
  - Web-плеер: стрим, API, текущая модель (100% лицензии с 2019)
  - Юридика: путь от UGC к лицензиям — что заставило перейти,
    пользовательское соглашение (написано юристами), страница
    правообладателям, процедура 5-дневного takedown
  - Выводы: какие тексты/процедуры адаптировать для DotSound
- [ ] **TRULA-music (trula-music.ru)**
  - Web-плеер: плеер + виджеты для стримеров
  - Юридика: оферта (ст. 1253.1), узкая ниша — как оформляют права
  - Выводы: что адаптировать для DotSound
- [ ] **Muzofond.fm / LightAudio.ru / HitMo (антипримеры)**
  - Web-плеер: открытый стрим, скачивание mp3
  - Юридика: нет явных лицензий, ссылаются на «пользователи
    загрузили», периодические блокировки Роскомнадзора
  - Выводы: какие ошибки НЕ повторять

### Итоговый отчёт (после анализа всех сервисов)

- [ ] Сводная таблица: сервис / web-API / возможность ретрансляции /
  юридическая модель / риски / что адаптировать
- [ ] Список конкретных текстов для адаптации: оферта, дисклеймер,
  страница правообладателям, форма загрузки с подтверждением прав
- [ ] Рекомендации по изменению архитектуры DotSound на основе анализа

## Юридическая готовность

- [x] Базовый legal package в репозитории
  - `LEGAL.md`
  - `LEGAL_AUDIT_RU.md`
  - `docs/legal/USER_AGREEMENT.md`
  - `docs/legal/PRIVACY_POLICY.md`
  - `docs/legal/COPYRIGHT_POLICY.md`
  - `docs/legal/UPLOAD_RULES.md`
  - `docs/legal/LEGAL_TEXTS.md`
- [x] Синхронизировать complaint/rightsholder flow во frontend и backend
  - `reason_type`, `rightsholder_name`, `proof_url` теперь проходят
    через schema -> route -> service -> repository -> UI
- [x] Обязательный акцепт условий при `UGC` upload
  - Checkbox в `UploadFileTab.tsx`
  - backend validation в `api/v1/tracks/user.py`
  - логирование версии условий в `track_upload_meta`
- [x] Постоянные guardrails для агентов и docs
  - `AGENTS.md`
  - `docs/ai-boundary-policy.md`
  - `.cursor/rules/legal-readiness.mdc`
- [x] Явно размечен current MVP external playback
  - В `Track` добавлены `access_mode`, `source_platform`,
    `canonical_source_url`
  - `SoundCloud` import помечает трек как
    `third_party_stream`
  - UI показывает внешний источник и режим доступа
- [x] На уровне модели разделены категории треков
  - В `Track` добавлен `catalog_type`
  - Базовое разделение: `ugc`, `licensed`, `external_reference`
  - `SoundCloud` -> `external_reference`, `upload/telegram` -> `ugc`
- [x] Опубликовать legal docs в самом продукте как отдельные доступные
  страницы
  - `/legal` стал hub-страницей
  - Добавлены маршруты `/legal/terms`, `/legal/privacy`,
    `/legal/copyright`, `/legal/upload-rules`
  - Upload и complaint flow теперь ссылаются на конкретные legal docs
- [x] Разделить на уровне модели/API `UGC`, `licensed` и
  `external-source` треки, не полагаясь только на текстовые
  дисклеймеры
- [x] Проверить current MVP с собственным playback поверх
  stream URL стороннего сервиса для текущего внешнего источника
  (`SoundCloud`) и зафиксировать residual risk
- [x] Разделить обычную пользовательскую жалобу и надлежащее
  уведомление правообладателя в отдельные UX и workflow
- [x] Базово разделить обычную жалобу и уведомление правообладателя
  в UX
  - `ComplaintModal` поддерживает режимы `user` и `rightsholder`
  - Правообладательский режим требует доп. поля и отдельный текст
- [x] Internal checklist для Terms внешних источников
  - `docs/legal/SOURCE_TERMS_CHECKLIST.md`
  - rule/docs привязаны к проверке external-source integrations
- [x] Сделать тексты внешнего импорта и поиска более честными
  - `SearchView` явно помечает SoundCloud как внешний источник
  - Текст предупреждает, что после добавления трек идёт как внешний
    поток стороннего сервиса

## DevOps / CI

- [x] GitHub Actions: lint + test на PR (Backend, Bot, PrivateCore)
- [ ] Автоматический деплой на VPS
- [x] Расширенный healthcheck (`/api/v1/health/deep` — БД, Redis, S3)
- [ ] Health monitoring + alerting (uptime check, внешний)

## Sprint 0..9 редизайна (2026-04, single-pass)

- [x] Bot: like/dislike — добавлен Bearer + правильный internal id
- [x] Frontend: `--progress` пробрасывается в `#pb-seek` (WebKit fix)
- [x] Frontend: SW unregister только в dev-режиме
- [x] Frontend: `env(safe-area-inset-bottom)` в `#nav`, `#player-bar`, `#main`
- [x] PrivateCore: `is_within_grace_period` отсекает будущие `deleted_at`
- [x] PrivateCore: `is_disposable_email` валидирует формат email
- [x] PrivateCore: тесты для `account_deletion_policy` (15 кейсов)
- [x] Backend: inline SQL вынесен из `artists.py`, `admin/audio_compute.py`
- [x] Backend: `dependencies.require_capability` использует репозиторий
- [x] Backend: `transcoding._upload_hls` использует `asyncio.to_thread`
- [x] Backend: `TrustedHostMiddleware` через `settings.allowed_hosts`
- [x] Bot: throttling middleware подключён к callback и inline_query
- [x] Bot: внутренний HTTP-сервер binds `127.0.0.1` (через config)
- [x] Bot: HTML escape во всех форматтерах (`base`, `audio`, `inline`, `stats`)
- [x] Bot: единый `mini_app_url` (убран `backend_base_url` для WebApp)
- [x] Bot: internal API возвращает opaque error codes
- [x] Bot: глобальный `errors` handler с user-friendly fallback
- [x] Bot: prefetched URLs используются в `_edit_audio_batch` (gap-less)
- [x] Bot: Dockerfile multi-stage с PrivateCore из родительской директории
- [x] Frontend: дизайн-токены в `tokens.css` (8pt grid, motion, type scale)
- [x] Frontend: `components.css` с Press, Sheet, Skeleton, EmptyState стилями
- [x] Frontend: `Press`, `Sheet`, `EmptyState`, `SkeletonList`, `OfflineBanner`
- [x] Frontend: расширен Icon-set (more-horizontal, queue, chevron-up/down)
- [x] Frontend: Unicode заменён на `<Icon>` в FullscreenLyrics, PlaylistsView,
  ComplaintModal, TrackCard, PlayerBar
- [x] Frontend: `installTelegramThemeBridge`, `installViewportListener`,
  `setBackButton`, `haptic`, `hapticNotification`
- [x] Frontend: PlayerBar v2 — overflow menu + breakpoints + skeleton hit-area
- [x] Frontend: TrackCard переключён на `usePlayerMeta` + `usePlayerActions`
- [x] Frontend: CoverImage с `loading="lazy"` + `width/height`
- [x] Frontend: aria-label/aria-pressed/aria-current на ключевых контролах
- [x] Frontend: `useConfirm` переписан с правильным unmount cleanup
- [x] Frontend: index.html splash сокращён с 1800ms до 1200ms safety cap
- [x] PrivateCore: README актуализирован, версия `0.2.0`, policy с
  bounded-transport exception
- [x] Backend: `/api/v1/health/deep` (DB / Redis / S3 ping)
- [x] Backend: `X-Request-ID` отдаётся в заголовке ответа
- [x] Docs: `docs/design-system.md`, `docs/redesign-rationale.md`

---

*Последнее обновление: 2026-04-19 агентом (admin i18n + auth race fix + admin refresh-on-boot).*

## Sprint admin / auth (2026-04-19)

- [x] Frontend: синхронный `api.restoreSession()` в `main.tsx` ДО рендера — убирает раннюю гонку токена с AdminProvider/PlayerProvider
- [x] Frontend: `AdminContext.tsx` гейтит `getAdminManifest()` на наличие токена и подписан на `app-auth-ready` + `i18n.languageChanged`; убран orphan-импорт `adminBundleUrl`
- [x] Frontend: `App.init()` пропускает `api.authTelegram('')` при пустом initData (убирает 422 + 500ms ретрай в ngrok-режиме)
- [x] Frontend: `connectWS(...)` вызывается сразу в `verifyTelegramCode` / `verifyMagicLink` / `verify2FA`, плюс диспатч `app-auth-ready`
- [x] Frontend: `restoreSession()` восстанавливает `auth-user-id` из JWT `sub`, если он потерян — убирает «при обновлении просит код»
- [x] Frontend: Suspense fallback с timeout-ом и retry в `App.tsx` (`RouteFallback`) — убирает «чёрный экран» при зависших lazy-чанках
- [x] Frontend: i18n RU/EN для всей админки (`admin.*` namespace в локалях, `useTranslation` в `AdminApp`, `AdminShell`, всех auth-формах и routes)
- [x] Frontend: `AuthGate` запускает `ensureCsrf` и `bootstrapMetadata` параллельно через `Promise.allSettled` и пытается `adminApi.refresh()` на старте — admin-сессия переживает reload без TOTP
- [x] Frontend: `useAdminAuth.capabilities` наполняется из манифеста после успешного refresh — `useCapability` теперь работает
- [x] Frontend: proactive refresh за 30 сек до expiry в `adminFetch`; при фейле refresh статус `'needs_login'` вместо `'unauth'`
- [x] Frontend: `AdminShell` — часы вынесены в изолированный `<Clock />`, остальная панель не перерисовывается каждую секунду
- [x] Frontend: refetchInterval поднят до 15-30 сек и `refetchIntervalInBackground: false` во всех админ-routes (Dashboard, Logs, Tasks, Metrics, Containers, Security, Settings, AudioCompute)
- [x] Frontend: удалён orphan-файл `frontend/src/admin/AdminDashboardView.tsx`
- [x] Frontend: `?nosw=1` в URL разрегистрирует service worker (отладка на ngrok)
