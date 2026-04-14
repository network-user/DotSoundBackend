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
- [ ] **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - Перенести inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - Перенести inline SQL из `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` в `services/repositories`

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

- [ ] **Английская версия сайта**
  - `react-i18next` + JSON-каталоги `ru.json` / `en.json`
  - Автоопределение языка: `navigator.language` + Telegram `language_code`
  - Хранение выбора: `localStorage` + поле `locale` в модели User
  - Переключатель языка в настройках

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
- [ ] **PWA-слой поверх текущего SPA**
  - `manifest.json` (name, icons 192/512, `display: standalone`, theme_color)
  - `<link rel="manifest">` в `index.html`
  - Service Worker через `vite-plugin-pwa`
  - Стратегия: `NetworkFirst` для API, `CacheFirst` для статики
  - Иконки: 192x192, 512x512, maskable
- [ ] Picture-in-Picture для видео-треков
  - `video.requestPictureInPicture()` в `TrackCardSheet.tsx`
- [ ] Offline-кэш треков (Service Worker)

## Видео к трекам

- [x] Загрузка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- [x] Удаление видео (`DELETE /tracks/{id}/video`)
- [x] Отдача видео (`GET /tracks/{id}/video`, proxy из S3)
- [x] UI: фоновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- [ ] **Оптимизация/сжатие видео**
  - Taskiq task `transcode_video`: FFmpeg H.264 + AAC
  - Два качества: 720p + 360p (CRF 23-28, `-preset medium`)
  - Генерация thumbnail (FFmpeg seek + один кадр)
  - `processing_status` для видео ("processing" -> "ready")
  - Placeholder в UI пока видео обрабатывается
- [ ] Увеличить лимит загрузки до 50-100MB
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

## Предзагрузка треков

- [x] Предзагрузка следующей пачки в боте (DotSoundBot)
- [x] `GET /tracks/{id}/adjacent` (sequential/shuffle/repeat_one)
- [x] hls.js с ABR (`startLevel: -1`, `enableWorker: true`)
- [ ] **Prefetch в Mini App / браузере**
  - Prefetch manifest следующего трека за ~15 сек до конца
  - Batch adjacent: `GET /tracks/{id}/adjacent?count=3`
  - Redis-кеш adjacent-списков (TTL 5 мин)

## Идентификация загрузчика

- [x] `uploaded_by_id` на Track (FK -> User с telegram_id)
- [x] `created_at` / `updated_at` timestamps
- [x] `RequestLoggingMiddleware` логирует `client_ip` в structlog
- [ ] **Расширенные метаданные загрузки (admin-only)**
  - Модель `TrackUploadMeta`: `upload_ip`, `upload_user_agent`
  - `upload_telegram_data` (JSONB, initData snapshot)
  - Заполнение при загрузке из `request.client.host` + headers
  - Admin endpoint для просмотра
  - Автоудаление через N дней (GDPR)
  - Retention-константа и условия удаления в PrivateCore, планировщик/удаление записей — в Backend

## Удаление аккаунта

- [ ] **Soft delete с grace period (30 дней)**
  - `DELETE /api/v1/users/me` -> `deleted_at` timestamp, `is_active = False`
  - Логин в течение 30 дней восстанавливает аккаунт
  - Taskiq job для hard delete после 30 дней
  - Grace period и decision "hard delete сейчас или нет" держать в PrivateCore
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

- [ ] **PlayerContext split (производительность)**
  - Разделить на `PlayerStateContext` (currentTime, duration, isPlaying),
    `PlayerActionsContext` (playTrack, togglePlay, seek -- useCallback),
    `PlayerMetaContext` (track, volume, EQ, модалки)
  - Или: `currentTime` в `useRef` + `useSyncExternalStore`
- [x] **LikesContext оптимизация**
  - `useMemo` на value, `useCallback` на все функции
- [ ] **React Router (deep links, PWA)**
  - `react-router-dom` v6
  - Маршруты: `/`, `/search`, `/upload`, `/liked`, `/playlists`,
    `/chats`, `/chats/:id`, `/profile`, `/profile/:userId`, `/track/:trackId`
  - `BottomNav` через `useNavigate`
  - Browser back/forward, shareable URLs
- [ ] **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView
  - `hls.js` в отдельный chunk (`manualChunks`)
  - Lazy-load модалок (TrackCardSheet, Equalizer, SettingsSheet)
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

## DevOps / CI

- [ ] GitHub Actions: lint + test на PR
- [ ] Автоматический деплой на VPS
- [ ] Health monitoring + alerting (uptime check)

---

*Последнее обновление: 2026-04-14 агентом (PrivateCore Boundary Audit & TODO Update)*
