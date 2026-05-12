# DotSoundBackend — Agent Context

## Проект
DotSound — музыкальная платформа в Telegram (SoundCloud-style, UGC, без рекламы).
Этот репозиторий: FastAPI-бэкенд, PostgreSQL, MinIO, Redis, Taskiq.
Связанные репозитории:
- `DotSoundBot` (Telegram-бот, aiogram 3)
- `DotSoundPrivateCore` (приватная бизнес-логика: алгоритмы, рекомендации, ML, scoring, anti-abuse)
- `DotSoundComputeWorker` (pull-based ASR-воркер: faster-whisper + опциональный Demucs; импортирует PrivateCore через path develop=true)

## Язык взаимодействия
- Агент отвечает пользователю на русском языке по умолчанию.
- Любые планы, чеклисты и пошаговые инструкции агент формулирует на русском языке.
- Переключение на другой язык допускается только по явному запросу пользователя в текущем чате.

## Тесты (конвенция для всех Python-репо)

- **Зеркало кода:** каталог `tests/<корневой_пакет>/` повторяет дерево пакета
  (здесь: `tests/app/...` ↔ `app/...`). Имена: `test_<модуль>.py` рядом с тестируемым слоем.
- **Корень `tests/`:** общий `conftest.py`, при необходимости вложенные
  `conftest.py` в тяжёлых подпакетах; общие фабрики — `tests/factories.py`.
- **Pytest:** `testpaths = ["tests"]`, `asyncio_mode = "auto"`; async-тесты с
  `pytestmark = pytest.mark.anyio` там, где принято в существующих модулях.
- **Покрытие:** `[tool.coverage.*]` в `pyproject.toml`, `source` = корневой пакет,
  `branch = true`, отчёт `coverage.xml` для CI. Шаблон отчёта по спринтам:
  `tests/SPRINT_TEST_REPORT_TEMPLATE.md`.

## TODO-трекер
- Файл `TODO.md` в корне — единый источник задач проекта.
- Агент обязан прочитать его в начале сессии и обновить после
  выполнения задач. Подробнее: `.cursor/rules/todo-tracking.mdc`.

## Жёсткие границы public/private
- Этот репозиторий — публичная витрина. Private логика живёт в
  `DotSoundPrivateCore`.
- Любой агент обязан соблюдать `docs/ai-boundary-policy.md`.
- Запрещено переносить private-код в public-ветку без явного
  подтверждения владельца.
- Если неясно, к какой зоне относится изменение, агент должен
  остановиться и запросить подтверждение.

## Секреты и `.env` (HARD RULE)
- `.env` и любые другие файлы с секретами (полный список —
  `.cursor/rules/secrets-and-env.mdc`) агенту трогать **запрещено**:
  ни читать, ни искать внутри, ни редактировать, ни переименовывать,
  ни откатывать через git, ни передавать в команды, ни цитировать
  содержимое в чате/коммитах/логах.
- Разрешены без спроса только `*.example` / `*.sample` / `*.template`,
  упоминания **имён** переменных в абстракции, и ссылка на путь к
  секретному файлу в конфиге (например, `env_file: - .env` в
  `docker-compose.yml`).
- Если для задачи нужно конкретное значение — агент обязан
  остановиться и попросить владельца либо вставить значение в чат,
  либо явно дать одноразовое разрешение на чтение конкретного файла.
- Разрешение действует только на текущую сессию и только на
  указанный файл; на следующий чат и на другие файлы оно не
  переносится.

## Legal readiness
- Юридические тексты и пользовательские дисклеймеры должны
  соответствовать фактической архитектуре.
- Если в продукте существует `UGC`-загрузка с хранением аудио,
  запрещено писать в UI или docs, что сервис не хранит аудиофайлы.
- Для внешних треков различать как минимум три режима:
  `UGC`, `licensed`, `external-source`.
- На уровне модели трека не полагаться только на `source`: различать
  также `catalog_type` и `access_mode`.
- При изменениях в `upload`, `import`, `playback`, `complaints`,
  `recommendation` и `LegalView` агент обязан проверить `LEGAL.md` и
  документы в `docs/legal/`.
- Собственный playback поверх stream URL стороннего сервиса считать
  high-risk моделью и не расширять без отдельной юридической оценки.
- До публичного релиза: **backlog** по 152-ФЗ — приведение
  **функционала** (ПДн, сроки, субпроцессоры, логи) в соответствие с
  требованиями к обработке после консультации с юристом; трекер —
  `TODO.md` (раздел «Соответствие 152-ФЗ / ПДн»), кратко —
  `docs/project_context.md`, `LEGAL.md`.

### Как классифицировать код

Перед написанием любого нового кода агент определяет зону:
- **Константа безопасности** (TTL, лимит попыток, cooldown,
  scope токена) -> `DotSoundPrivateCore`
- **Функция-решение** (burn? cooldown? disposable? internal IP?)
  -> `DotSoundPrivateCore`
- **Anti-abuse / модерация** (правила фильтрации, детекции,
  auto-hide) -> `DotSoundPrivateCore`
- **Allowlist / blocklist** (допустимые MIME-типы, опасные
  расширения, размерные лимиты) -> `DotSoundPrivateCore`
- **Redis/DB/HTTP вызов** -> `DotSoundBackend` (adapter)
- **Schema / Model / SQL** -> `DotSoundBackend`
- **Библиотечный вызов** (magic bytes detection, FFmpeg,
  Pillow, HTTP-клиент) -> `DotSoundBackend` (transport)
- **HTTPException / FastAPI-специфичный код** -> `DotSoundBackend`

Паттерн: PrivateCore = правила, Backend = транспорт.

### Пример: Upload Security

**ПРАВИЛЬНО:**
```
PrivateCore (upload_policy.py):
  ALLOWED_AUDIO_MIMES = frozenset({...})  # константа
  DANGEROUS_EXTENSIONS = frozenset({...}) # константа
  is_audio_mime_allowed(mime) -> bool      # решение
  is_extension_dangerous(name) -> bool     # решение

Backend (file_validator.py):
  magic.from_buffer(data, mime=True)       # transport
  if not is_audio_mime_allowed(detected):  # вызов PrivateCore
      raise HTTPException(415, ...)        # FastAPI transport
```

**НЕПРАВИЛЬНО:**
```
Backend (file_validator.py):
  _ALLOWED_MIMES = frozenset({...})  # ← константа в Backend!
  def _is_dangerous(name): ...       # ← решение в Backend!
```

Если при добавлении security-логики агент сомневается --
остановиться и спросить: "Это правило или транспорт?"

### Source attribution исключение (карточка артиста)

Для карточки артиста разрешено явно показывать имя источника
(`source_name`) и прямую ссылку (`source_page_url`) на страницу,
с которой взяты данные. Это узкое исключение из общего black-box
правила: пользователь должен видеть, откуда взяты сведения, и
иметь возможность переключаться между источниками.

Ограничения:

- Раскрываются только публичные `source_name` и `source_page_url`,
  которые приходят из PrivateCore. Имена внутренних стадий,
  веса скоринга, порядок fallback и другие детали пайплайна
  не утекают.
- Исключение действует только на карточке артиста (UI + соответствующее
  API). Остальные каскады (lyrics, recommendations, anti-abuse и т.д.)
  остаются строго opaque.
- Новые внешние источники в публичный список атрибуции добавляются
  только после явного review.

### Текущие модули PrivateCore
- `services/auth_policy.py` -- auth constants + decision functions
- `services/abuse.py` -- disposable email, Tor policy
- `services/moderation.py` -- content moderation rules
- `services/web_auth.py` -- OTP generation, IP masking, UA parsing
- `services/internal_bridge.py` -- URL/header builders
- `services/import_rules.py` -- import limits
- `services/catalog_sync_policy.py` -- caps for external catalog sync runs
  and admin enqueue cooldown; `app/services/artist_catalog_sync_service.py`,
  `app/services/admin_artist_catalog_service.py`
- `services/recommendation_engine.py` + `recommendation_language_policy.py` --
  recsys scoring, listening-language heuristics; питают
  `app/services/recommendation_service.py` и
  `app/repositories/recommendation.py` (транспорт/пул)
- `services/playcount_policy.py` -- публичный учёт
  прослушиваний (qualify) + ранжирование плейлиста
  «Выбор пользователей»; `app/services/public_playcount_service.py`,
  `app/api/v1/recommendations.py`
- `services/playback_health_policy.py` -- пороги серверных
  ошибок воспроизведения и длительность авто-сокрытия; используется в
  `app/services/track_playback_health_service.py`
- `services/playlist_cover_policy.py` -- одноразовая автогенерация
  коллажа-обложки для пользовательских плейлистов (`should_attempt_auto_playlist_cover`);
  используется в `app/services/playlist_service.py`
- `services/upload_policy.py` -- upload security: MIME allowlists,
  dangerous extensions, size limits, decision functions
- `services/admin_security_policy.py` -- TTL admin-сессии, окно
  TOTP, lockout, step-up freshness, alert decisions, PII-redact
  для audit-payload. Подключён по всему backend (admin_auth_service,
  admin_device_service, admin_alert_service, admin_manifest_service,
  ws.py, observability.py). Временный stub
  `app/core/_admin_security_constants.py` удалён.
- `services/asr_policy.py` -- cascade-ASR tier order, SpeechKit
  budget gate, per-job cost estimate. Используется в
  `app/services/lyrics_cascade.py`,
  `app/services/lyrics_worker.py`,
  `app/services/asr_speechkit_adapter.py`.
- `services/listener_stats_policy.py` -- допустимые периоды
  личной статистики (`period_days`), порог топа по периоду,
  нижняя граница времени для агрегатов (календарные сутки для
  `period_days=1`). Используется в `app/services/listener_stats_service.py`.
- `services/network_policy.py` -- CIDR validation + IP-in-CIDR
  helper. Питает `app/middlewares/internal_api_allowlist.py` и
  per-worker IP allowlist в
  `app/services/compute_worker_service.verify_worker_request`.
- `services/compute_anomaly_policy.py` -- пороги детектора
  аномалий воркеров (processing_too_fast, duplicate_result,
  failure_rate, stale_after_claim) + `should_auto_suspend`.
  Используется в `app/services/compute_anomaly_service.py`.
- `contracts/` -- protocol constants

## Стек
- Python 3.12
- FastAPI (async, OpenAPI)
- SQLAlchemy 2.x async + asyncpg
- Alembic (миграции)
- aioboto3 (MinIO S3 async)
- Taskiq + Redis (фоновые задачи, транскодирование)
- pydantic-settings (конфиг из .env)
- structlog (логирование)
- slowapi (rate limiting через Redis)
- Инфраструктура: Docker Compose (PostgreSQL 16, MinIO, Redis 7)

## Соглашения кода
- Линтер: **Ruff** | Форматтер: **Black** | Type checker: **Mypy strict**
- Длина строки: **79 символов**
- **Без комментариев** — код самодокументируется через имена
- Докстринги только там, где сигнатура не передаёт смысл
- **Полная асинхронность**: async/await везде
- Настройки только через `app/config.py` (pydantic-settings)
- `os.environ` напрямую — запрещено
- **Без эмодзи в UI** — вместо дефолтных эмодзи используем монохромные SVG иконки из `components/Icon/Icon.tsx`. Все иконки stroke-based, currentColor. Стиль проекта: **минимализм, монохром**

## Архитектурная модель (Telegram-style)

Проект следует модели Telegram: открытый клиент + приватное ядро.

```
Frontend (React)  →  Backend API (FastAPI)  →  PrivateCore (pure Python)
   открытый UI        открытый транспорт         приватные правила
```

- **Frontend** (`frontend/`) — полностью открытый, собирается
  независимо (`npm run build`). Общается с Backend только через
  `/api/v1/` REST и WebSocket.
- **Backend** (`app/`) — открытый транспортный слой. Маршрутизация,
  Redis/DB/S3 операции, Pydantic-схемы. Не содержит бизнес-правил.
- **PrivateCore** (`DotSoundPrivateCore`) — приватное ядро.
  Константы, decision functions, anti-abuse, модерация. Чистый
  Python без фреймворков.

## Архитектурные слои Backend
```
api/v1/ → services/ → repositories/ → models/
```
- `api/v1/` — HTTP граница: парсинг запроса, вызов сервиса, возврат схемы
- `services/` — оркестрация. Вызывает репозитории и PrivateCore
- `repositories/` — только запросы к БД. Возвращает ORM-модели
- `models/` — определения таблиц SQLAlchemy
- `schemas/` — Pydantic модели запросов/ответов

### Правило слоёв
- `api/v1/` НЕ должен содержать `select()`, `session.execute()`,
  или прямые ORM-запросы. Вся работа с БД — через services/repos.
- `services/` импортирует decision functions из PrivateCore.
- `repositories/` — чистые SQL-запросы без бизнес-решений.

### Известные нарушения (tech debt)
- (нет открытых на данный момент)

Закрыто:
- `internal/audio_compute.py` — inline ORM перенесён в
  `AudioComputeRepository`/`compute_worker_service`. Routes
  делают только верификацию + dispatch.
- `admin/tracks.py`, `admin/users.py`, `admin/complaints.py` —
 inline SQL вынесен в `AdminService` + `AdminRepository`
 (см. `app/services/admin_service.py`, `app/repositories/admin.py`)
- `metadata.py:get_popular_genres` — реализован в
 `AdminRepository.get_popular_genres` (доступен как admin
 endpoint в Phase 3)
- `users.py:get_login_history` — реализован через
 `AdminActionLogRepository` + admin endpoint
 `/api/v1/admin/users-ext/{user_id}/login-history`

## Правила DI
- Сессии БД только через `dependencies.get_db()`
- S3-клиент только через `app/core/s3.py` (`get_s3_client()`)
- `app = create_app()` — фабрика. Тесты создают свой экземпляр

## Безопасность
- `DEBUG=true` в .env включает dev-режим (mock auth, мягкие проверки)
- `DEBUG=false` — продакшн: JWT_SECRET обязан быть сменён, mock-эндпоинты отключены
- CORS настраивается через `ALLOWED_ORIGINS` в .env
- Rate limiting через Redis (работает при нескольких воркерах)

## Структура репозитория
```
DotSoundBackend/
├── app/
│   ├── main.py              # create_app() -> FastAPI, lifespan
│   ├── config.py            # AppSettings(BaseSettings)
│   ├── dependencies.py      # get_db, get_settings, get_current_user
│   ├── api/
│   │   ├── router.py        # api_router prefix="/api/v1"
│   │   └── v1/
│   │       ├── health.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── likes.py
│   │       ├── dislikes.py
│   │       ├── playlists.py
│   │       ├── soundcloud.py
│   │       ├── complaints.py
│   │       ├── metadata.py
│   │       ├── lyrics.py
│   │       ├── follows.py
│   │       ├── albums.py
│   │       ├── admin/
│   │       │   ├── tracks.py
│   │       │   ├── users.py
│   │       │   └── complaints.py
│   │       └── tracks/
│   │           ├── discovery.py
│   │           ├── user.py
│   │           ├── hls.py
│   │           └── playback.py
│   ├── core/
│   │   ├── db.py            # async_engine, AsyncSessionLocal
│   │   ├── s3.py            # S3 operations + ensure_bucket_exists
│   │   ├── auth.py          # JWT + Telegram HMAC
│   │   ├── logging.py       # structlog configuration
│   │   ├── rate_limit.py    # slowapi + Redis
│   │   └── tkq.py           # Taskiq Redis broker
│   ├── middlewares/
│   │   └── request_logging.py
│   ├── models/
│   │   ├── base.py          # Base, TimestampMixin
│   │   ├── user.py
│   │   ├── track.py
│   │   ├── album.py
│   │   ├── playlist.py
│   │   ├── like.py
│   │   ├── dislike.py
│   │   ├── follow.py
│   │   ├── lyrics.py
│   │   └── complaint.py
│   ├── repositories/        # DB access layer
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # Business logic
│   └── static/mini_app/     # Mini App (HTML/CSS/JS)
├── alembic/                  # Migrations (10 versions)
├── frontend/                 # React/Vite Mini App
├── scripts/                  # Operational helpers
├── tests/                    # pytest + anyio
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Запуск локально

### 1. Первоначальная настройка
```bash
copy .env.example .env        # создать .env из шаблона
poetry install                 # установить зависимости
```

### 2. Инфраструктура (Docker)
```bash
docker compose up -d postgres minio redis
```

### 3. Миграции БД
```bash
poetry run alembic upgrade head
```

### 4. Бэкенд (терминал 1)
```bash
poetry run python main.py
```
API доступен на http://localhost:8000

### 5. Frontend / Mini App (терминал 2)
```bash
cd frontend
npm install
npm run dev
```
Mini App доступен на http://localhost:5173/mini_app/

### 6. Бот (отдельный репозиторий DotSoundBot, терминал 3)
Из корня **этого** репозитория (DotSoundBackend):
```bash
cd ../DotSoundBot
python main.py
```
(В PowerShell: `cd ..\\DotSoundBot` или `Set-Location ..\\DotSoundBot`.)

### Быстрый запуск через Makefile
```bash
make init    # первый раз: .env + docker + миграции
make dev     # инфра + миграции + бэкенд
make test    # тесты
make lint    # Ruff + Black + mypy
make format  # автоформатирование
```

### Для Telegram (HTTPS через ngrok)
```bash
ngrok http 5173
```
Полученный URL вписать в `.env` бота как `MINI_APP_URL`.
