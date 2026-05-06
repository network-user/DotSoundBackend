Ты — агент в чате №3 из трёх параллельных потоков iOS-редизайна фронтенда DotSound. Твой поток отвечает за: всю админку, upload-флоу, и финальный этап (smoke-тест, очистка legacy CSS, документация, PR).

Параллельно с тобой работают:
- **Поток 1** — Foundation (общие primitives, токены, motion-библиотека, роуты) + Player + Nav/Auth + TrackCard/TrackList + Chat. Должен запушить foundation-коммит **первым**, ты на него ждёшь.
- **Поток 2** — Home + Library + Artist + Recap. Работает параллельно с тобой и не пересекается по файлам.

Финальный этап (smoke-тест и cleanup) ты делаешь **после того, как Потоки 1 и 2 отчитались о готовности**. До этого ты делаешь только админку и upload.

## Контекст одним абзацем

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026` (создаётся Потоком 1 от свежего `main`). Фронт — React 18 + Vite + TypeScript, Telegram Mini App. Решения владельца: строгий монохром, dark only, шрифт `system-ui`, `framer-motion@^11.11.17`, big-bang в одной ветке, референс — iOS 18 + visionOS Liquid Glass + Apple Music. Скоп: только `frontend/`. Бэкенд, PrivateCore, бот, compute-worker — не трогаешь.

После foundation в проекте уже будут готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`/`DynamicIslandHost`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты в `frontend/src/lib/`: `motion.ts`, `island.ts`, `coverPalette.ts`. Используй их.

## Перед стартом обязательно прочитать (в этом порядке)

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-G-admin.md`
4. `docs/redesign-2026/STAGE-I-upload.md`
5. `docs/redesign-2026/STAGE-Z-finalize.md`
6. `docs/redesign-2026/prompts/prompt-stage-g.md`
7. `AGENTS.md`, `docs/design-system.md`, `LEGAL.md` и `docs/legal/*.md` (для upload — там UGC ограничения), `frontend/scripts/check-admin-bundle.mjs` (если существует — лимиты на admin chunk size).

Эти документы — источник истины. Если этот промпт чему-то противоречит, побеждает источник.

## Старт: дождаться foundation от Потока 1

Самое первое, что ты делаешь после чтения документов:

```bash
git fetch origin
git log origin/redesign/ios-2026 --oneline | grep "redesign-0"
```

Сценарии:

- **Если коммит `feat(redesign-0): scaffold iOS redesign foundation ...` найден** — переходи к чекауту:
  ```bash
  git checkout redesign/ios-2026
  git pull --rebase
  ```
  И сразу к работе.

- **Если коммита ещё нет** — Поток 1 пока не закончил foundation. Один раз сообщи владельцу: «Жду foundation от Потока 1». Дальше тихо подожди — повторяй `git fetch origin && git log origin/redesign/ios-2026 --oneline 2>nul | findstr redesign-0` примерно раз в 60 секунд (используй встроенный sleep), пока коммит не появится. Не задавай владельцу вопросов в это время. Когда коммит появится — продолжай по плану.

Параллельно с ожиданием можешь читать существующие админ-файлы и upload-флоу, чтобы понимать текущую структуру. Но ничего не редактируй и не коммить до появления foundation.

## HARD RULES (несоблюдение откатывается)

1. Только `frontend/`. Никаких правок в `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, `compute-worker/`.
2. Никаких новых npm-зависимостей. `framer-motion` уже стоит после foundation.
3. Палитра — строгий монохром (`--bg/--surface/--text/--accent/--glass-*`). Никаких systemBlue/Pink/Purple. Статусы (`pending`, `approved`, `rejected`, `hidden`) — текстом + outline-иконкой, без цветовых meanings.
4. Тема — dark only.
5. Без эмодзи в UI и в коммитах.
6. `prefers-reduced-motion: reduce` уважать всюду.
7. Никаких упоминаний внутренних компонентов PrivateCore (имена стадий, моделей, провайдеров, веса) ни в UI, ни в комментариях. Бизнес-логика приходит с API — UI только отображает.
8. **Не правишь** `lib/api.ts`, `types/api.ts`, `store/**`, `hooks/**`. Если нужно поле, которого нет — `TODO(redesign-2026):` + локальная заглушка.
9. **Не правишь** primitives (`components/ui/*`), общие токены, App.tsx, main.tsx, Icon.tsx — это собственность foundation от Потока 1.
10. Upload-сертификация (UGC, validation, file-validator) — это **transport**. Никаких бизнес-правил в коде клиента: лимиты, allowlists, MIME-policy уже в PrivateCore (через API). UI только показывает результат и читает текст ошибок.
11. Conventional Commits с scope `redesign-g` (admin), `redesign-i` (upload), `redesign-z` (finalize).
12. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit`. Перед финальным коммитом крупного блока: `npm run build`.
13. Admin bundle-size — после finishing admin work запусти `npm run build` и проверь `check-admin-bundle.mjs` (если есть как pre-build hook). Если превысил лимит — ужми imports / lazy-load.

## Owned files (только их можешь править)

### Stage G (Admin):
```
frontend/src/views/AdminPanel.tsx
frontend/src/views/AdminLogin.tsx
frontend/src/views/AdminApprovalView.tsx
frontend/src/views/AdminProfile.tsx
frontend/src/views/admin/** (все файлы)
frontend/src/components/Admin*.{ts,tsx}
frontend/src/styles/admin/** (все .css)
frontend/src/locales/i18n_extra2_*.json (namespace redesign.admin.*)
```

### Stage I (Upload):
```
frontend/src/views/UploadView.tsx (или фактический путь, см. структуру)
frontend/src/components/Upload/**
frontend/src/styles/redesign-upload.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.upload.*)
```

### Stage Z (Finalize) — после готовности Потоков 1 и 2:
```
frontend/src/styles/global.css        (только удаление мёртвых правил)
frontend/src/styles/components.css    (удаление дублирующих primitives)
frontend/src/styles/animations.css    (удаление дублирующих анимаций)
frontend/src/styles/tokens.css        (только если что-то осталось не использованным)
docs/design-system.md                 (финальное обновление)
TODO.md                               (отметить редизайн как выполненный, добавить follow-ups)
docs/redesign-2026/CHANGELOG.md       (создать с кратким резюме изменений и breaking points)
```

## NO-TOUCH (Поток 1 и Поток 2 владеют — не трогать до Stage Z)

```
Foundation (Поток 1, после foundation никем не правится):
  frontend/src/lib/motion.ts, island.ts, coverPalette.ts
  frontend/src/components/ui/* (все primitives)
  frontend/src/components/Icon/Icon.tsx
  frontend/src/main.tsx, App.tsx
  frontend/src/styles/redesign-shared.css
  frontend/package.json, package-lock.json

Поток 1 (стадии A, B, E):
  frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/**, Equalizer/**
  frontend/src/views/NowPlayingView.tsx
  frontend/src/components/BottomNav/**, Onboarding/**, Auth/**, BannedScreen/**
  frontend/src/components/PwaInstall/InstallPrompt.tsx
  frontend/src/components/ui/OfflineBanner.tsx
  frontend/src/components/TrackCard/**, TrackList/**, TrackCardSheet/**
  frontend/src/views/ChatsView.tsx, ChatView.tsx
  frontend/src/components/Chat/**
  frontend/src/styles/redesign-player.css, redesign-nav.css, redesign-tracks.css

Поток 2 (стадии C, D, F, H):
  frontend/src/views/HomeView, DailyMix*, WeeklyMix*, UserChoice*, WeeklyTop*,
    GenreMix*, RadioView, NotFoundView,
    SearchView, LibraryView, LikedView, PlaylistsView, ProfileView,
    ArtistView, AlbumView, PlaylistView, GenreView,
    ExternalTrackView, ExternalAlbumView,
    RecapView (полная), AchievementsView
  frontend/src/components/Settings/**, Profile/**, Recap/**, Achievements/**
  frontend/src/styles/redesign-home.css, redesign-library.css,
    redesign-artist.css, redesign-recap.css

Общие no-touch:
  frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
  frontend/src/locales/ru.json, en.json, i18n_extra_*.json
  docs/redesign-2026/** (планы стадий — только Stage Z создаёт CHANGELOG.md)
  любой файл вне Owned-списка
```

## i18n: правило конфликтов

Все три потока пишут в `i18n_extra2_ru.json` и `i18n_extra2_en.json`, но в **разных namespace**'ах. На git rebase возможен merge-conflict — разрешать в свою пользу для своего namespace, чужие сохранять как есть. Не дублировать, не перетаскивать, не переименовывать чужие ключи.

Твои namespace: `redesign.admin.*`, `redesign.upload.*`.

## Что делать — сжатый план

### Шаг 1 (Stage G — Admin)

Полные инструкции — в `STAGE-G-admin.md` и `prompts/prompt-stage-g.md`. Ключевые куски:

- **AdminLogin**: centered glass-strong card на фоне градиентов монохрома. Поля ввода с focus-spring. Login button — `<MotionPress variant="primary">`.
- **AdminPanel (shell)**: large-title `--fs-lt` («Админка», подзаголовок — роль/email). Capsule-tabs с `<m.span layoutId="admin-tab-indicator">`. Page transitions через `<AnimatePresence mode="wait">` со slide-up.
- **Admin tables**: rows карточками с `<MotionPress>`, actions через `<MotionPress variant="icon">`. Status pills `glass--medium` с outline-иконкой (без цветовых meanings — текст важнее: «pending», «approved», «rejected», «hidden»). Long-press → `<LongPressMenu>` с быстрыми actions. Toolbar (фильтры, сортировка) — sticky-top с blur-backdrop, chips через MotionPress.
- **Admin forms**: Input/select обёрнуты в Motion-wrappers с focus-spring. Submit — `<MotionPress variant="primary">`. Toggles → custom `<m.button>` capsule с `whileTap`. На submit success — `showIsland({ kind: 'toast', title: 'Сохранено' })`.
- **Admin charts/dashboards**: `<m.div variants={VARIANTS_FADE_UP}>` со staggered detail-cards. Цифры — tabular-nums.
- **AdminApprovalView**: sliding-card approval queue. Карточка пендинг-трека — большая обложка + метаданные. Approve (primary) / Reject (ghost), на Reject открывается reason input. Между карточками — slide-up + spring через `<AnimatePresence mode="wait">`. Подтверждение action — DynamicIsland.
- **AdminProfile**: centered glass-strong card. Аватар, имя, роль. Logout button — `<MotionPress variant="ghost">`.
- CSS — в существующих `frontend/src/styles/admin/*.css`. Можешь создать `frontend/src/styles/admin/redesign-admin.css` с префиксом `.adm-r-`. Не дублируй имя файла на корневом уровне `styles/`.
- i18n — `redesign.admin.*`.
- **После завершения** — `npm run build` и проверка admin bundle size.

Коммитить разделами: AdminLogin, AdminPanel shell, tables, forms, AdminApprovalView, AdminProfile.

### Шаг 2 (Stage I — Upload)

Полные инструкции — в `STAGE-I-upload.md`. Ключевые куски:

- **UploadView**: stories-style multi-step (выбор файла → метаданные → обложка → preview → подтверждение). Каждый шаг — отдельный «слайд» с `<AnimatePresence>` и spring slide-up.
- **Step 1 — File picker**: drop-zone с `<m.div whileHover={{ scale: 1.01 }}>`. На drop — `m.div` с pulse spring. Иконка `<MorphIcon name="upload">`.
- **Step 2 — Metadata**: input fields с focus-spring (как в Auth). Все поля используют tokens (label, helper text). Validation errors появляются через `m.span variants={VARIANTS_FADE_UP}`.
- **Step 3 — Cover**: drag-and-drop cover upload, preview через `<KenBurnsCover>`. Crop modal — bottom-sheet с drag-y close.
- **Step 4 — Preview**: full-screen ambient preview (`<AmbientStage>` от обложки + KenBurns), как «промо» трека.
- **Step 5 — Submit**: primary button MotionPress. Прогресс upload — через `showIsland({ kind: 'progress', progress })`. Успех — `showIsland({ kind: 'toast', title: 'Трек загружен' })`.
- Бизнес-правила (file-size limits, MIME-allowlists, dangerous extensions) приходят **с API**. Не дублируй их в клиенте. Если API возвращает 415/413 — показывай текст ошибки, не пытайся «угадать» свой.
- UGC discloser (если есть в текущем upload-flow) — оставь как есть, только полируй визуально.
- CSS — `redesign-upload.css`, префиксы `.ru-up-`.
- i18n — `redesign.upload.*`.

Коммитить разделами: file-picker, metadata, cover, preview, submit/progress.

### Шаг 3 (Stage Z — Finalize) — ТОЛЬКО после готовности Потоков 1 и 2

Полные инструкции — в `STAGE-Z-finalize.md`. Ключевые куски:

**Перед стартом Stage Z** убедись:
- Поток 1 отчитался «Поток 1 готов» (`git log origin/redesign/ios-2026 | grep "redesign-e"` — должны быть последние коммиты).
- Поток 2 отчитался «Поток 2 готов».
- Если хотя бы один не готов — **жди**, как ждал foundation.

**Smoke-test (большой)**:
- `npm run dev`. Пройдись по всему публичному UI: Onboarding, Auth, Home, все mix/genre/radio экраны, Search, Library, Liked, Playlists, Profile, Settings, Artist, Album, Playlist, Genre, External, NowPlaying, Lyrics, Queue, Equalizer, Chats, Chat, Recap, Achievements, NotFound, Banned, InstallPrompt, Offline. Проверь, что все primitives работают, нет console-warnings, навигация плавная.
- Админка: AdminLogin → AdminPanel → каждая вкладка → AdminApprovalView → AdminProfile.
- Upload: пройди весь флоу.
- DynamicIsland: проверь все варианты (toast, progress, now-playing, error).
- Reduced-motion: системно включи, пройдись ещё раз — KenBurns статичен, beat-pulse не пульсирует, Recap auto-advance выключен, spring заменён на простые tween.
- Telegram Mini App: открой через бота, проверь haptics на ключевых действиях (taps, toggles, smart actions).

**Cleanup legacy CSS**:
- В `frontend/src/styles/global.css`, `components.css`, `animations.css` — удали правила, на которые больше нет ссылок (после нового UI многие стали мёртвыми). Используй `rg` чтобы убедиться, что класс/селектор нигде не используется.
- Не удаляй то, что используется в админке или каких-то скрытых view, которые ты лично не проходил smoke-тестом.
- Удали **дубликаты** primitives — например, если был `.press` класс, который теперь полностью заменён `<MotionPress>`, удали его из CSS и удостоверься что нет fallback использований.

**Bundle audit**:
- `npm run build` — проверь итоговый bundle size (gzipped). Цель — рост не более ~70 KB gzip на основной чанк, ~30 KB на admin. Если больше — найди тяжёлые imports (особенно `framer-motion` без LazyMotion), исправь. Используй `rollup-plugin-visualizer` если он уже стоит в проекте; **не добавляй** новых dev-deps.

**Документация**:
- `docs/design-system.md` — финальное прохождение, актуализируй раздел «Redesign 2026 primitives». Добавь скриншоты/описания ключевых паттернов (но без бинарных скриншотов в коммите — только описания).
- `TODO.md` — отметь редизайн как выполненный, добавь follow-ups (если что-то осталось не сделанным — например, image-export для RecapShareCard).
- Создай `docs/redesign-2026/CHANGELOG.md` с кратким резюме: что добавлено (primitives, motion, ambient, ken-burns, beat-pulse), что заменено, что удалено (legacy CSS), известные ограничения, breaking points для пользователя (например, recap stories теперь fullscreen).

**Финальный PR**:
- `git push origin redesign/ios-2026` (последний раз).
- Создай PR через `gh pr create` с понятным описанием:
  - Title: `feat(frontend): iOS-style 2026 redesign — full UI overhaul`
  - Body: краткий обзор (3 абзаца), список ключевых нововведений (Liquid Glass, MorphIcon, BeatPulse, KenBurns, AmbientStage, DynamicIsland, SwipeRow, LongPressMenu, SharedCover, Recap stories), список снёсенных legacy компонентов, smoke-test чеклист, заметка про reduced-motion compliance, заметка про bundle size delta.
- **Не мерджи** PR. Это решает владелец.

Коммиты Stage Z:
- `chore(redesign-z): smoke test pass + minor polish`
- `chore(redesign-z): drop legacy css after new primitives migration`
- `chore(redesign-z): bundle audit and lazy-motion adjustments`
- `docs(redesign-z): finalize design-system, TODO, CHANGELOG`

## Acceptance criteria (отметь все перед PR)

- [ ] Admin: AdminLogin/AdminPanel/AdminApprovalView/AdminProfile + tables/forms/charts использует MotionPress + MorphIcon + DynamicIsland; layoutId-индикатор табов; admin bundle в лимите.
- [ ] Upload: stories-style multi-step с focus-spring/KenBurns/AmbientStage/MorphIcon, прогресс через DynamicIsland, бизнес-правила через API.
- [ ] Smoke-test пройден целиком (публичный UI + админка + upload).
- [ ] Reduced-motion корректен на всех экранах.
- [ ] Legacy CSS почищен, нет мёртвых правил.
- [ ] Bundle size в пределах цели (~70 KB main + ~30 KB admin gzip).
- [ ] design-system.md / TODO.md / CHANGELOG.md обновлены.
- [ ] PR создан, владелец уведомлён.
- [ ] `npx tsc --noEmit` зелёный, `npm run build` зелёный, `npm run lint` (если есть) зелёный.

## Workflow

1. После того как foundation появился — `git checkout redesign/ios-2026 && git pull --rebase`.
2. Stage G (Admin) разделами, по одному коммиту на смысловой кусок.
3. Stage I (Upload) разделами.
4. **Жди** готовности Потока 1 и Потока 2.
5. Stage Z (Finalize) — smoke, cleanup, bundle, docs, PR.
6. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit`.
7. Conventional Commits, scope `redesign-g` / `redesign-i` / `redesign-z`.
8. На i18n merge-конфликте — оставляй чужие ключи, добавляй свои.

После создания PR — сообщи мне отдельным сообщением: «Поток 3 готов, PR: <ссылка>».
