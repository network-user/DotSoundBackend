Ты — агент в чате №1 из трёх параллельных потоков iOS-редизайна фронтенда DotSound. Твой поток запускается **первым**. Сначала ты делаешь общий фундамент (после него запускаются Потоки 2 и 3), затем берёшь свою долю экранов: плеер, навигация/auth, карточка трека, чаты.

## Контекст одним абзацем

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка для всей работы: `redesign/ios-2026` (создаёшь её ты, от свежего `main`). Фронт — React 18 + Vite + TypeScript, Telegram Mini App. Уже есть дизайн-токены, мотион-токены, glass-токены, базовые primitives. Владелец принял решения: строгий монохром, dark only, шрифт `system-ui` (без лицензий), `framer-motion@^11.11.17`, big-bang в одной ветке, референс — iOS 18 + visionOS Liquid Glass + Apple Music. Скоп: только `frontend/`. Бэкенд, PrivateCore, бот, compute-worker — не трогаешь.

## Перед стартом обязательно прочитать (в этом порядке)

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-0-foundation.md`
4. `docs/redesign-2026/STAGE-A-player.md`
5. `docs/redesign-2026/STAGE-B-nav-auth.md`
6. `docs/redesign-2026/STAGE-E-tracks-chat.md`
7. `docs/redesign-2026/prompts/prompt-stage-0.md`, `prompt-stage-a.md`, `prompt-stage-b.md`, `prompt-stage-e.md`
8. `AGENTS.md`, `docs/design-system.md`

Эти документы — источник истины. Если этот промпт чему-то противоречит, побеждает источник.

## HARD RULES (несоблюдение откатывается)

1. Только `frontend/`. Никаких правок в `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, `compute-worker/`.
2. Никаких новых npm-зависимостей кроме `framer-motion@^11.11.17` (ставится в фундаменте).
3. Палитра — строгий монохром (`--bg/--surface/--text/--accent/--glass-*`). Никаких systemBlue/Pink/Purple.
4. Тема — dark only.
5. Без эмодзи в UI, в коммитах, в reactions (вместо emoji-реакций — монохромные `MorphIcon`).
6. `prefers-reduced-motion: reduce` уважать всюду: spring выключать, KenBurns статичен, beat-pulse выключен, swipe rubber-band не пружинит.
7. Никаких упоминаний внутренних провайдеров, моделей, стадий PrivateCore — ни в коде, ни в комментариях, ни в коммитах. Это публичный фронт.
8. **Не правишь** `lib/api.ts`, `types/api.ts`, `store/**`, `hooks/**`. Если нужно поле, которого нет — `TODO(redesign-2026):` + локальная заглушка.
9. Conventional Commits с scope `redesign-0` для фундамента, `redesign-a/b/e` для соответствующих стадий.
10. Каждый коммит перед push: `git pull --rebase` + `npx tsc --noEmit`. Перед финальным коммитом стадии: `npm run build`.

## Параллельный мир: кто что делает

- **Поток 1 (ты)** — Foundation (Stage-0) → Player (A) → Nav/Auth (B) → Tracks/Chat (E).
- **Поток 2** — Home (C) → Library (D) → Artist (F) → Recap (H). Стартует **после** твоего foundation-коммита.
- **Поток 3** — Admin (G) → Upload (I) → Finalize (Z). Стартует **после** твоего foundation-коммита; финализацию (Z) делает в конце, когда Потоки 1 и 2 готовы.

После того как foundation запушен, **сразу сообщи владельцу одним сообщением** «Foundation готов, можно запускать Потоки 2 и 3», и продолжай работу над A → B → E.

## Owned files (только их можешь править)

### Foundation (Stage-0):
```
frontend/package.json, package-lock.json (только добавление framer-motion)
frontend/src/styles/tokens.css        (расширить, не ломать существующее)
frontend/src/styles/global.css        (только правка font-family в body)
frontend/src/lib/motion.ts            (создать)
frontend/src/lib/island.ts            (создать)
frontend/src/lib/coverPalette.ts      (создать)
frontend/src/components/ui/MotionPress.tsx, MorphIcon.tsx, SwipeRow.tsx,
  LongPressMenu.tsx, DynamicIsland.tsx, AmbientStage.tsx, KenBurnsCover.tsx,
  BeatPulse.tsx, HorizontalSnap.tsx, SharedCover.tsx (создать все)
frontend/src/components/Icon/Icon.tsx (расширить PATHS и FILLED_ICONS)
frontend/src/views/NowPlayingView.tsx (stub)
frontend/src/views/RecapView.tsx       (stub — Поток 2 заменит на полную)
frontend/src/App.tsx                   (роуты + DynamicIslandHost)
frontend/src/main.tsx                  (LazyMotion + новые css импорты)
frontend/src/styles/redesign-shared.css (общие классы primitives)
frontend/src/styles/redesign-player.css, redesign-nav.css, redesign-home.css,
  redesign-library.css, redesign-tracks.css, redesign-artist.css,
  redesign-recap.css, redesign-upload.css (создать пустыми с шапкой)
frontend/src/locales/i18n_extra2_ru.json, i18n_extra2_en.json (namespace каркас)
docs/design-system.md (раздел «Redesign 2026 primitives»)
```

### Stage A (Player):
```
frontend/src/components/PlayerBar/PlayerBar.tsx
frontend/src/components/FullscreenLyrics/**
frontend/src/components/QueueSheet/QueueSheet.tsx
frontend/src/components/Equalizer/Equalizer.tsx
frontend/src/views/NowPlayingView.tsx (полная реализация)
frontend/src/styles/redesign-player.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.player.*)
```

### Stage B (Nav/Auth):
```
frontend/src/components/BottomNav/BottomNav.tsx
frontend/src/components/Onboarding/**
frontend/src/components/Auth/**
frontend/src/components/BannedScreen/**
frontend/src/components/PwaInstall/InstallPrompt.tsx
frontend/src/components/ui/OfflineBanner.tsx
frontend/src/styles/redesign-nav.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.nav.*)
```

### Stage E (Tracks/Chat):
```
frontend/src/components/TrackCard/TrackCard.tsx, TrackCardSheet.tsx
frontend/src/components/TrackList/TrackList.tsx (+ подкомпоненты)
frontend/src/views/ChatsView.tsx, ChatView.tsx
frontend/src/components/Chat/**
frontend/src/styles/redesign-tracks.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.tracks.*)
```

## NO-TOUCH (Потоки 2 и 3 владеют)

```
Поток 2 (после foundation):
  frontend/src/views/HomeView, DailyMixView, WeeklyMixView, UserChoiceView,
    WeeklyTopView, GenreMixView, RadioView, NotFoundView,
    SearchView, LibraryView, LikedView, PlaylistsView, ProfileView,
    ArtistView, AlbumView, PlaylistView, GenreView,
    ExternalTrackView, ExternalAlbumView,
    AchievementsView (полная RecapView заменяет stub)
  frontend/src/components/Settings/**, Profile/**, Recap/**, Achievements/**
  frontend/src/styles/redesign-home.css, redesign-library.css,
    redesign-artist.css, redesign-recap.css

Поток 3 (после foundation):
  frontend/src/views/AdminPanel, AdminLogin, AdminApprovalView, AdminProfile,
    admin/**, UploadView (+ модули)
  frontend/src/components/Admin*.tsx, Upload/**
  frontend/src/styles/admin/**, redesign-upload.css

Общие no-touch (после foundation):
  frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
  frontend/src/main.tsx, App.tsx (после foundation никто не трогает)
  frontend/src/locales/ru.json, en.json, i18n_extra_*.json
  frontend/src/components/Icon/Icon.tsx (после foundation никто не правит)
  frontend/src/styles/tokens.css, global.css, components.css, animations.css,
    redesign-shared.css (после foundation никто не правит)
  frontend/src/components/ui/* (после foundation никто не правит)
  frontend/src/lib/motion.ts, island.ts, coverPalette.ts (после foundation)
  docs/redesign-2026/** (планы стадий)
```

## i18n: правило конфликтов

Все три потока пишут в `i18n_extra2_ru.json` и `i18n_extra2_en.json`, но в **разных namespace**'ах. На git rebase возможен merge-conflict — разрешать в свою пользу для своего namespace, чужие сохранять как есть. Не дублировать, не перетаскивать, не переименовывать чужие ключи.

Твои namespace: `redesign.player.*`, `redesign.nav.*`, `redesign.tracks.*`.

## Что делать — сжатый план

### Шаг 0 (Foundation, Stage-0)

Полные инструкции — в `docs/redesign-2026/STAGE-0-foundation.md` и `docs/redesign-2026/prompts/prompt-stage-0.md`. Ключевые пункты:

1. `git checkout -b redesign/ios-2026 origin/main` (или fetch + checkout existing).
2. `cd frontend && npm install framer-motion@^11.11.17 --save`.
3. Расширить `tokens.css`: `--font-stack-system`, `--fs-lt: 34px`, `--fs-tt: 28px`, `--ls-display: -0.022em`, `--ls-tight: -0.014em`, `--ls-snug: -0.006em`.
4. В `global.css` поменять `body { font-family: var(--font-stack-system); }` — больше ничего.
5. Создать `lib/motion.ts` с `SPRING_GENTLE/SNAPPY/BOUNCY/LAYOUT`, `TWEEN_FAST/SLOW`, `VARIANTS_FADE_UP/SCALE_IN/PAGE_SLIDE/SHEET_SLIDE_UP`, реэкспорт `m`, `LazyMotion`, `domAnimation`, `useReducedMotion`.
6. Создать `lib/island.ts` (`showIsland/dismissIsland`) и `components/ui/DynamicIsland.tsx` + `DynamicIslandHost.tsx` — pill сверху с safe-area-inset, layout-anim для shape-shift.
7. Создать `lib/coverPalette.ts` — canvas 32×32 downsample, гистограмма, top-3 кластера, десатурация до ~30%, кэш в Map, fallback `null`.
8. Создать все primitives в `components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Все используют `m` из `lib/motion`.
9. Расширить `Icon.tsx`: filled-пары для `heart`, `play`, `pause`, `star`, `bookmark`, `home`, `search`, `library`, `chats`, `profile`, `radio`, `users-following`, `flame`. Outline `bookmark`, `chevron-left`, `chevron-right`. Абстрактные: `dots`, `grip`, `add-to-queue`, `headphones`, `wave`, `disc`, `chart-bar`, `gear-alt`, `share-arrow`, `airplay-like`. `FILLED_ICONS` Set дополнить.
10. Создать stub `views/NowPlayingView.tsx` и `views/RecapView.tsx` (named exports `NowPlayingView`, `RecapView`).
11. В `App.tsx`: lazy-импорты для `/now-playing` и `/recap`, регистрация роутов, монтирование `<DynamicIslandHost />` рядом с `<OfflineBanner />`.
12. CSS-каркас: создать пустые `redesign-shared.css` (с общими классами primitives), `redesign-player.css`, `redesign-nav.css`, `redesign-home.css`, `redesign-library.css`, `redesign-tracks.css`, `redesign-artist.css`, `redesign-recap.css`, `redesign-upload.css`. Импорты добавить в `main.tsx`.
13. В `main.tsx` обернуть `<App />` в `<LazyMotion features={domAnimation}>`.
14. В `i18n_extra2_*.json` добавить пустые namespace: `redesign.player`, `redesign.nav`, `redesign.home`, `redesign.library`, `redesign.tracks`, `redesign.artist`, `redesign.recap`, `redesign.upload`, `redesign.admin`, `redesign.achievements`. Deep-merge с существующим, не перезаписывать.
15. В `docs/design-system.md` добавить раздел «Redesign 2026 primitives» со списком и кратким API. Не дублировать SHARED-CONTRACTS.
16. Smoke: `npx tsc --noEmit`, `npm run build`, `npm run dev` — проверить /now-playing, /recap, `showIsland`.
17. Один большой коммит:
    ```
    git add -A
    git commit -m "feat(redesign-0): scaffold iOS redesign foundation (motion, primitives, tokens, routes)"
    git push -u origin redesign/ios-2026
    ```
18. **СРАЗУ** сообщи владельцу: «Foundation готов, можно запускать Потоки 2 и 3».

### Шаг 1 (Stage A, Player)

Полные инструкции — в `STAGE-A-player.md` и `prompts/prompt-stage-a.md`. Ключевые куски:

- **PlayerBar v3**: Liquid Glass подложка, ambient-glow от обложки, `<BeatPulse>` на иконке Play, scrub с rubber-band, все кнопки → `<MotionPress>`, play/pause → `<MorphIcon name="play" filled={isPlaying}>`, like → `<MorphIcon name="heart" filled={liked}>`, мини-обложка → `<SharedCover trackId={...}>`.
- **NowPlayingView (полный экран)**: открывается по свайпу-вверх (drag-y). Фон — `<AmbientStage>` + `<KenBurnsCover>`. Большая обложка через `<SharedCover>` (layout-shared с PlayerBar). Сегментированный контрол: Now Playing / Lyrics / Queue. Drag-down закрывает (порог 120 px → `navigate(-1)`). Like-burst spring + scale.
- **FullscreenLyrics**: layout как Apple Music (маленькая обложка слева, контролы справа). Активная строка — `m.span layout` со spring. Beat-pulse на маленькой обложке.
- **QueueSheet**: slide-up через `VARIANTS_SHEET_SLIDE_UP`. Каждый ряд — `<SwipeRow rightAction={trash, destructive}>`. Текущий трек — beat-pulse-индикатор.
- **Equalizer**: bottom-sheet с drag-y, drag-down закрывает. Слайдеры со spring-pop. Toggle-pill через `<MotionPress>`.
- CSS — `redesign-player.css`, префиксы `.rp-player-`, `.rp-now-`, `.rp-queue-`, `.rp-eq-`.
- i18n — `redesign.player.*`.

Коммитить разделами: PlayerBar, NowPlaying, Lyrics, Queue, Equalizer.

### Шаг 2 (Stage B, Nav/Auth)

Полные инструкции — в `STAGE-B-nav-auth.md` и `prompts/prompt-stage-b.md`. Ключевые куски:

- **BottomNav v3**: Liquid Glass, иконки → `<MorphIcon filled={active}>`, `<m.span layoutId="bn-indicator">` под активным, haptic `selection` на смену таба, captions с tabular-nums где счётчики.
- **AuthScreen / EmailAuth / TelegramAuth**: KenBurnsCover на градиентном фоне монохрома, поля ввода с focus-spring (расширение поля при focus), loader → `showIsland({ kind: 'progress' })`.
- **Onboarding**: stories-style, swipe between, `<AnimatePresence>` с direction-aware variants. OnboardingGenreScreen — chips с spring scale на pick. ImportStep — `<MorphIcon>` платформ + `<DynamicIsland kind="progress">`.
- **BannedScreen**: glass-strong card, большой outlined `lock`, монохром.
- **InstallPrompt**: glass-medium + `VARIANTS_FADE_UP`.
- **OfflineBanner**: переписать на `showIsland({ kind: 'error', durationMs: Infinity })`. Сам компонент остаётся точкой монтирования effect-а.
- CSS — `redesign-nav.css`, префиксы `.rb-nav-`, `.rb-auth-`, `.rb-ob-`, `.rb-ban-`, `.rb-install-`.
- i18n — `redesign.nav.*`.

### Шаг 3 (Stage E, Tracks/Chat)

Полные инструкции — в `STAGE-E-tracks-chat.md` и `prompts/prompt-stage-e.md`. Ключевые куски:

- **TrackCard**: два варианта (`compact` / `expanded`). Обёртка `<MotionPress variant="subtle">`. Cover → `<SharedCover trackId={track.id}>`. Если `isCurrent && isPlaying` — мини-обложка в `<BeatPulse bpm={track.bpm ?? 120} active>`. Long-press → `<LongPressMenu>` (Like / Add to playlist / Add to queue / Share / Hide / Report). Like → `<MorphIcon name="heart" filled={liked}>`.
- **TrackList**: каждый row → `<SwipeRow leftAction={heart} rightAction={queue}>`. Для liked-flavor — `leftAction.icon='heart-fill'` + «Снять лайк». «Сейчас играет» → beat-pulse-индикатор.
- **TrackCardSheet**: `<KenBurnsCover>` поверх `<AmbientStage>`. Drag-down закрывает (порог 100 px). Primary action на Play, ghost на Add to queue/Like/Share.
- **ChatsView**: rows со swipe (`leftAction=pin`, `rightAction=archive`), long-press → `<LongPressMenu>` (Mute / Pin / Mark unread / Delete). Sticky-header large-title.
- **ChatView**: iMessage-bubbles **строго монохром**. Own — alignSelf:flex-end, ярко-серый фон. Peer — alignSelf:flex-start, glass-фон. На отправку — `m.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}` со spring. Reactions — long-press → `<LongPressMenu>` с **монохромными `<MorphIcon>`** (никаких emoji). Composer: capsule input, Send → `<MotionPress variant="primary">` с `<MorphIcon name="arrow-up" filled />`.
- CSS — `redesign-tracks.css`, префиксы `.re-tc-`, `.re-tl-`, `.re-tcs-`, `.re-chats-`, `.re-chat-`, `.re-bubble-`.
- i18n — `redesign.tracks.*`.

## Acceptance criteria (отметь все перед финальным push)

- [ ] Foundation: `framer-motion` в lock, primitives собираются, DynamicIslandHost смонтирован, /now-playing и /recap stub-роуты открываются, `npm run build` зелёный.
- [ ] Player: PlayerBar (Liquid Glass + MorphIcon + BeatPulse + SharedCover), NowPlaying с табами и drag-down close, Lyrics с активной строкой spring, Queue со swipe-actions, Equalizer как bottom-sheet.
- [ ] Nav/Auth: BottomNav (морф + layoutId-индикатор), Auth (focus-spring), Onboarding (stories-style), Banned/Install (glass + motion), OfflineBanner на DynamicIsland.
- [ ] Tracks/Chat: TrackCard (SharedCover + BeatPulse + LongPressMenu), TrackList (SwipeRow), TrackCardSheet (KenBurns + AmbientStage), Chats/Chat в iMessage-стиле с монохром-bubbles и monochrome-reactions.
- [ ] reduced-motion корректен на всех экранах.
- [ ] `npx tsc --noEmit` зелёный, `npm run build` зелёный.
- [ ] Нет упоминаний внутренних компонентов PrivateCore.

## Workflow

1. Запусти foundation (Stage-0) одним коммитом, push, **сообщи владельцу**.
2. Дальше — раздел за разделом, по одному коммиту на смысловой кусок.
3. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Перед финальным коммитом каждого крупного блока: `npm run build`.
5. Conventional Commits, scope = `redesign-0`, `redesign-a`, `redesign-b`, `redesign-e`.
6. Push после каждого коммита.

Когда все acceptance criteria выполнены — сообщи мне отдельным сообщением «Поток 1 готов».
