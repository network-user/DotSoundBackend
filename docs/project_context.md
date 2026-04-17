# DotSound — Project Context (auto-generated 2026-04-16)

> Открывать при каждом новом сеансе. Обновлять при архитектурных изменениях.

---

## Что такое DotSound

Музыкальная платформа в стиле Telegram: открытый клиент (Backend) + закрытая логика (PrivateCore).
Пользователи загружают треки, слушают, ставят лайки, общаются в чатах, видят текст песни с таймкодами.

---

## Два репозитория

| Репо | Путь | Роль |
|------|------|------|
| **DotSoundBackend** | `C:\Users\User\PycharmProjects\DotSoundBackend` | FastAPI + React + PostgreSQL + Redis + MinIO |
| **DotSoundPrivateCore** | `C:\Users\User\PycharmProjects\DotSoundPrivateCore` | Чистый Python, без фреймворков. Алгоритмы, константы, политики |

**Правило:** Backend импортирует из PrivateCore. PrivateCore ничего не знает о FastAPI/SQLAlchemy.

---

## Стек Backend

- **API:** FastAPI (Python 3.12), async/await
- **БД:** PostgreSQL 14+, SQLAlchemy 2.x async, Alembic миграции
- **Очередь:** Redis + Taskiq (воркеры: transcoding, lyrics, cover, import)
- **Хранилище:** MinIO (S3-совместимый)
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
  repositories/    ← DB-запросы
  models/          ← SQLAlchemy модели
  schemas/         ← Pydantic схемы
  core/            ← db, auth, s3, ws_manager, taskiq broker
frontend/src/
  components/      ← UI компоненты
  views/           ← страницы (Home, Search, Upload, ...)
  store/           ← PlayerContext, LikesContext, lyricsTaskStore
  lib/api.ts       ← ВСЕ API-вызовы (1226 строк)
  lib/ws.ts        ← WebSocket с авто-реконнектом
```

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

## Lyrics — как работает (со стороны Backend)

1. Пользователь нажимает "Авто-генерация"
2. Backend ставит задачу в Taskiq → `generate_lyrics_task`
3. При необходимости Backend скачивает аудио трека во временный файл
   (источник: S3 или внешний URL, зависит от трека)
4. Воркер вызывает `PrivateCore.generate_lyrics(artist, title, audio_path)`
   и получает обратно текст + опциональные синхронизированные строки
5. Результат → PostgreSQL (`track_lyrics.synced_lines` JSONB)
6. Фронтенд поллит `/lyrics/auto/status/{track_id}` каждые 2 сек

Всё, что относится к источникам текста, распознаванию и
сопоставлению — внутренняя реализация PrivateCore и в этом
документе не описывается.

---

## Известные проблемы (актуально на 2026-04-16)

| # | Проблема | Файл | Приоритет |
|---|----------|------|-----------|
| 1 | Avatar upload заморожен (hardcode 501) | `app/api/v1/users.py` | 🔴 Высокий |
| 2 | WS handlers не отписываются → утечка памяти | `frontend/src/lib/ws.ts` | 🔴 Высокий |
| 3 | play_count в ответе — устаревшее значение | `app/api/v1/tracks/playback.py` | 🟠 Средний |
| 4 | Race condition на счётчике жалоб | `app/services/complaint_service.py` | 🟠 Средний |
| 5 | `.catch(() => {})` везде — пользователь не видит ошибки | Много компонентов фронта | 🟠 Средний |
| 6 | "error" vs "not_found" в lyrics generation не различаются в UI | `lyricsTaskStore.ts` | 🟠 Средний |
| 7 | Нет аудита admin-действий | `app/api/v1/admin/` | 🟡 Низкий |
| 8 | Нет ротации ключей шифрования чата | `message_service.py` | 🟡 Низкий |
| 9 | Grace period при удалении аккаунта не показывается пользователю | `users.py` + frontend | 🟡 Низкий |

---

## Модели данных (ключевые)

| Модель | Особенности |
|--------|-------------|
| `User` | telegram_id ИЛИ email обязательны (CHECK constraint). `deleted_at` = мягкое удаление |
| `Track` | `processing_status`, `source` (internal/soundcloud), `access_mode`. HLS ключи в S3 |
| `TrackLyrics` | 1:1 с Track. `synced_lines` JSONB = `[{time_ms, text}]`. `source` = manual/auto |
| `Message` | `content` зашифрован ChaCha20 |
| `ImportJob` | Статус bulk-импорта из Telegram/SoundCloud |

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

| Задача | Триггер |
|--------|---------|
| `transcode_audio` | После загрузки трека |
| `transcode_video` | После загрузки видео |
| `generate_and_upload_cover` | Нет обложки |
| `generate_lyrics_task` | Кнопка авто-генерации |
| `generate_lyrics_debug_task` | Debug UI (изолированный запуск отдельной стадии провайдера) |
| `import_soundcloud_track` | Импорт по URL |
| `import_telegram_profile` | Сканирование профиля бота |

---

## ENV переменные (критические)

| Переменная | Где используется |
|-----------|----------------|
| `JWT_SECRET` | Backend: подпись JWT |
| `TELEGRAM_BOT_TOKEN` | Backend: верификация Telegram HMAC |
| `RESEND_API_KEY` | Backend: отправка email |
| `TOTP_ENCRYPTION_KEY` | Backend: шифрование TOTP secret |
| `CHAT_ENCRYPTION_KEY` | Backend: шифрование сообщений |
| `DEBUG` | Backend: разрешает mock auth и debug endpoints |

Переменные окружения, относящиеся к PrivateCore, описаны внутри
самого PrivateCore (см. `DotSoundPrivateCore/.env.example`) и здесь
не дублируются по правилу чёрного ящика.

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
