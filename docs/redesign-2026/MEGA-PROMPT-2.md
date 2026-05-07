Ты — агент в чате №2 из трёх параллельных потоков iOS-редизайна фронтенда DotSound. Твой поток отвечает за «контентную» половину публичного приложения: Home/Discovery/Radio, Library/Search/Profile/Settings, Artist/Album/Playlist/Genre/External, Recap/Achievements.

Параллельно с тобой работают:
- **Поток 1** — Foundation (общие primitives, токены, motion-библиотека, роуты) + Player + Nav/Auth + TrackCard/TrackList + Chat. Должен запушить foundation-коммит **первым**, ты на него ждёшь.
- **Поток 3** — Admin + Upload + Finalize. Работает параллельно с тобой и не пересекается по файлам.

## Контекст одним абзацем

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026` (создаётся Потоком 1 от свежего `main`). Фронт — React 18 + Vite + TypeScript, Telegram Mini App. Решения владельца: строгий монохром, dark only, шрифт `system-ui`, `framer-motion@^11.11.17`, big-bang в одной ветке, референс — iOS 18 + visionOS Liquid Glass + Apple Music. Скоп: только `frontend/`. Бэкенд, PrivateCore, бот, compute-worker — не трогаешь.

После foundation у тебя в проекте уже будут готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`/`DynamicIslandHost`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты в `frontend/src/lib/`: `motion.ts` (spring-presets, варианты, `m`, `LazyMotion`, `domAnimation`, `useReducedMotion`), `island.ts` (`showIsland`/`dismissIsland`), `coverPalette.ts`. Используй их.

## Перед стартом обязательно прочитать (в этом порядке)

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-C-home.md`
4. `docs/redesign-2026/STAGE-D-library.md`
5. `docs/redesign-2026/STAGE-F-artist.md`
6. `docs/redesign-2026/STAGE-H-recap.md`
7. `docs/redesign-2026/prompts/prompt-stage-c.md`, `prompt-stage-d.md`, `prompt-stage-f.md`, `prompt-stage-h.md`
8. `AGENTS.md`, `docs/design-system.md`

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

Параллельно с ожиданием можешь читать существующие файлы своих будущих экранов (HomeView.tsx, LibraryView.tsx и т.д.), чтобы понимать текущую структуру и не делать лишнего ресёрча после старта. Но ничего не редактируй и не коммить до появления foundation.

## HARD RULES (несоблюдение откатывается)

1. Только `frontend/`. Никаких правок в `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, `compute-worker/`.
2. Никаких новых npm-зависимостей. `framer-motion` уже стоит после foundation.
3. Палитра — строгий монохром (`--bg/--surface/--text/--accent/--glass-*`). Никаких systemBlue/Pink/Purple.
4. Тема — dark only.
5. Без эмодзи в UI и в коммитах.
6. `prefers-reduced-motion: reduce` уважать всюду: spring выключать, KenBurns статичен, beat-pulse выключен, parallax/auto-advance выключены.
7. Никаких упоминаний внутренних провайдеров, моделей, стадий PrivateCore. Recap-логика, recsys, listening-language — это всё opaque, UI получает готовые цифры от API. На карточке артиста разрешено показывать только публичные `source_name` / `source_page_url` (см. AGENTS.md → Source attribution исключение).
8. **Не правишь** `lib/api.ts`, `types/api.ts`, `store/**`, `hooks/**`. Если нужно поле, которого нет — `TODO(redesign-2026):` + локальная заглушка.
9. **Не правишь** primitives (`components/ui/*`), общие токены, App.tsx, main.tsx, Icon.tsx — это собственность foundation от Потока 1.
10. `TrackCard` / `TrackList` / `TrackCardSheet` — собственность Потока 1. Можешь их **использовать** как есть и **обернуть** снаружи (например, в `m.div`), но **внутрь не лезть**.
11. Conventional Commits с scope `redesign-c` / `redesign-d` / `redesign-f` / `redesign-h` соответственно стадии.
12. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit`. Перед финальным коммитом крупного блока: `npm run build`.

## Owned files (только их можешь править)

### Stage C (Home / Discovery / Radio):
```
frontend/src/views/HomeView.tsx
frontend/src/views/DailyMixView.tsx
frontend/src/views/WeeklyMixView.tsx
frontend/src/views/UserChoiceView.tsx
frontend/src/views/WeeklyTopView.tsx
frontend/src/views/GenreMixView.tsx
frontend/src/views/RadioView.tsx
frontend/src/views/NotFoundView.tsx
frontend/src/styles/redesign-home.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.home.*)
```

### Stage D (Library / Search / Profile / Settings):
```
frontend/src/views/SearchView.tsx
frontend/src/views/LibraryView.tsx
frontend/src/views/LikedView.tsx
frontend/src/views/PlaylistsView.tsx
frontend/src/views/ProfileView.tsx
frontend/src/components/Settings/**
frontend/src/components/Profile/**
frontend/src/styles/redesign-library.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.library.*)
```

### Stage F (Artist / Album / Playlist / Genre / External):
```
frontend/src/views/ArtistView.tsx
frontend/src/views/AlbumView.tsx
frontend/src/views/PlaylistView.tsx
frontend/src/views/GenreView.tsx
frontend/src/views/ExternalTrackView.tsx
frontend/src/views/ExternalAlbumView.tsx
frontend/src/components/Artist/** (если есть)
frontend/src/components/Album/** (если есть)
frontend/src/styles/redesign-artist.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.artist.*)
```

### Stage H (Recap / Achievements):
```
frontend/src/views/RecapView.tsx        (заменяет stub)
frontend/src/views/AchievementsView.tsx
frontend/src/components/Recap/**
frontend/src/components/Achievements/**
frontend/src/styles/redesign-recap.css
frontend/src/locales/i18n_extra2_*.json (namespace redesign.recap.*)
```

## NO-TOUCH (Поток 1 и Поток 3 владеют — не трогать)

```
Foundation (Поток 1, после foundation никем не правится):
  frontend/src/lib/motion.ts, island.ts, coverPalette.ts
  frontend/src/components/ui/* (все primitives)
  frontend/src/components/Icon/Icon.tsx
  frontend/src/main.tsx, App.tsx
  frontend/src/styles/tokens.css, global.css, components.css, animations.css,
    redesign-shared.css
  frontend/package.json, package-lock.json

Поток 1 (стадии A, B, E):
  frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/**, Equalizer/**
  frontend/src/views/NowPlayingView.tsx (полная реализация)
  frontend/src/components/BottomNav/**, Onboarding/**, Auth/**, BannedScreen/**
  frontend/src/components/PwaInstall/InstallPrompt.tsx
  frontend/src/components/ui/OfflineBanner.tsx
  frontend/src/components/TrackCard/**, TrackList/**, TrackCardSheet/**
  frontend/src/views/ChatsView.tsx, ChatView.tsx
  frontend/src/components/Chat/**
  frontend/src/styles/redesign-player.css, redesign-nav.css, redesign-tracks.css

Поток 3 (стадии G, I, Z):
  frontend/src/views/AdminPanel*, AdminLogin*, AdminApprovalView*, AdminProfile*
  frontend/src/views/admin/**
  frontend/src/components/Admin*.{ts,tsx}
  frontend/src/views/UploadView.tsx (+ модули)
  frontend/src/components/Upload/**
  frontend/src/styles/admin/**, redesign-upload.css

Общие no-touch:
  frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
  frontend/src/locales/ru.json, en.json, i18n_extra_*.json
  docs/redesign-2026/** (планы стадий)
  любой файл вне Owned-списка
```

## i18n: правило конфликтов

Все три потока пишут в `i18n_extra2_ru.json` и `i18n_extra2_en.json`, но в **разных namespace**'ах. На git rebase возможен merge-conflict — разрешать в свою пользу для своего namespace, чужие сохранять как есть. Не дублировать, не перетаскивать, не переименовывать чужие ключи.

Твои namespace: `redesign.home.*`, `redesign.library.*`, `redesign.artist.*`, `redesign.recap.*` (и `redesign.achievements.*` если такой namespace создан в foundation).

## Что делать — сжатый план

### Шаг 1 (Stage C — Home / Discovery / Radio)

Полные инструкции — в `STAGE-C-home.md` и `prompts/prompt-stage-c.md`. Ключевые куски:

- **HomeView v3**: hero-карточка дня (большая обложка, `<AmbientStage coverUrl={hero.cover_url}>` + `<KenBurnsCover>`, large-title + primary CTA «Слушать» через `<MotionPress variant="primary">`). Quick-grid 4–6 ярлыков (Liked, Daily, Weekly, Radio, User-choice, Weekly-top) — карточки `glass--medium` с `<MorphIcon filled />`. Секционные карусели через `<HorizontalSnap parallax pageDots>`: dailyMix, weeklyMix, userChoice, weeklyTop, genre-mixes, followed-artists strip.
- **DailyMix/WeeklyMix/UserChoice/WeeklyTop/GenreMix Views**: hero (AmbientStage + KenBurns + большая обложка), TrackList снизу обёрнутый в `<m.div variants={VARIANTS_FADE_UP} initial="hidden" animate="visible">`. Над TrackList — Play all (primary) + Shuffle (ghost). Используй существующие методы PlayerContext через хуки.
- **RadioView**: вращающийся диск-обложка через KenBurns, BeatPulse в центре. Quick-стартеры — 6 «настроений» (chill, focus, gym, cinematic, retro, acoustic) карточками `glass--liquid` с морф-иконками.
- **NotFoundView**: центрированная иллюстрация text-only, large-title, MotionPress «На главную».
- CSS — `redesign-home.css`, префиксы `.rh-home-`, `.rh-mix-`, `.rh-radio-`, `.rh-nf-`.
- i18n — `redesign.home.*`.

Коммитить разделами: HomeView, mix-views, RadioView, NotFoundView.

### Шаг 2 (Stage D — Library / Search / Profile / Settings)

Полные инструкции — в `STAGE-D-library.md` и `prompts/prompt-stage-d.md`. Ключевые куски:

- **SearchView**: sticky-header с capsule-input (`glass--medium`), focus растягивает поле через `m.input animate={{ scaleX: 1.02 }}`. Chips-фильтры (треки/артисты/альбомы/плейлисты/внешние) — активный с filled `<MorphIcon>`, все через `<MotionPress>`. Результаты — секции с staggered `VARIANTS_FADE_UP`.
- **LibraryView**: capsule-tabs с `<m.span layoutId="lib-tab-indicator">` под активным. Внутри вкладок — rows в `<SwipeRow>` (Liked: heart/queue, Playlists: play/trash, Mine: optional share).
- **LikedView**: sticky-header с metadata + sort chips. TrackList со swipe-actions (TrackList — собственность Потока 1, **внутрь не лезть**, оборачивать row снаружи нельзя; у TrackList уже есть встроенный SwipeRow через Поток 1).
- **PlaylistsView**: grid 2-col больших обложек, long-press → `<LongPressMenu>` (Переименовать / Дублировать / Удалить).
- **ProfileView**: hero с большим аватаром (128 px) + KenBurnsCover на абстрактной градиентной подложке монохрома. Имя — `--fs-lt`. Секции (Stats, My tracks, My playlists, Followed artists) — карточки `glass--medium` с MotionPress. «Поделиться профилем» — `<MotionPress variant="ghost">`.
- **Settings**: каждая секция — карточки с MotionPress rows. Toggles → custom `<m.button>` с capsule-scale `whileTap`. Haptic на каждое значимое действие. Подтверждения сохранения через `showIsland({ kind: 'toast', title: 'Сохранено', durationMs: 2000 })`.
- CSS — `redesign-library.css`, префиксы `.rd-search-`, `.rd-lib-`, `.rd-liked-`, `.rd-pl-`, `.rd-profile-`, `.rd-settings-`.
- i18n — `redesign.library.*`.

Коммитить разделами: Search, Library, Liked, Playlists, Profile, Settings.

### Шаг 3 (Stage F — Artist / Album / Playlist / Genre / External)

Полные инструкции — в `STAGE-F-artist.md` и `prompts/prompt-stage-f.md`. Ключевые куски:

- **ArtistView**: header в Apple-Music-стиле — большой `<KenBurnsCover>` поверх `<AmbientStage coverUrl={...}>`, sticky-blur при скролле (через `useScroll` + `useTransform`, либо CSS-only sticky + backdrop-filter). Имя `--fs-lt`. Под ним — followers, source_name (если есть в API — ссылка через `<MotionPress variant="ghost">` на `source_page_url`). Action row: Play / Shuffle / Follow (последний — toggle outline↔filled). Секции с staggered fade-up: Top tracks (TrackList — Поток 1), Albums (`<HorizontalSnap parallax>`), Artist info, Similar artists. Внизу — Report / Open external.
- **AlbumView**: hero обложка с KenBurns + AmbientStage, под header — TrackList. Action row: Play all / Shuffle / Like / Add to library.
- **PlaylistView**: collage 2×2 из 4 обложек как hero + KenBurns + AmbientStage. Description, owner-info, follower count. Action row: Play / Shuffle / Follow / Edit (если owner). TrackList со swipe-actions.
- **GenreView**: декоративный fullscreen-градиент монохрома + KenBurns на текстуре. Табы (Top tracks / New / Artists) с `<m.span layoutId="genre-tab-indicator">`.
- **ExternalTrackView / ExternalAlbumView**: hero + KenBurns + AmbientStage. Бейдж `external` / `licensed` — pill `glass--medium` с outline-иконкой `link-external`. Source attribution — `<MotionPress variant="ghost">` на `source_page_url` (открывает через `window.Telegram.WebApp.openLink`). Если у трека есть Lyrics — кнопка открывает `<FullscreenLyrics>`/`<TrackCardSheet>` (компоненты Потока 1).
- CSS — `redesign-artist.css`, префиксы `.rf-artist-`, `.rf-album-`, `.rf-playlist-`, `.rf-genre-`, `.rf-external-`.
- i18n — `redesign.artist.*`.

Коммитить разделами: Artist, Album, Playlist, Genre, External.

### Шаг 4 (Stage H — Recap / Achievements)

Полные инструкции — в `STAGE-H-recap.md` и `prompts/prompt-stage-h.md`. Ключевые куски:

- **RecapView**: полноэкранная stories-механика. 8–12 слайдов, авто-переход 5 с (прогрессбар-pill сверху для каждого слайда: `m.div animate={{ scaleX: [0, 1] }} transition={{ duration: 5, ease: 'linear' }}`). Tap left → previous, tap right → next, long-press — pause auto-progress. `<AnimatePresence mode="wait">` для смены слайдов (slide-up + crossfade). Слайды: Intro → Total minutes (большая цифра с пульсацией) → Top 3 artists (HorizontalSnap из больших аватаров) → Top 5 tracks (стек обложек с KenBurns + BeatPulse) → Most played (full-screen AmbientStage + KenBurns + beat-pulse) → Top genres (motion bar-chart) → Mood/time-of-day гистограм → Friends/comparison (если есть в API) → Outro/share с CTA «Поделиться».
- **RecapShareCard**: вертикальная карточка 9:16, коллаж обложек + большие монохромные цифры + DotSound watermark. Кнопки «Сохранить» / «Поделиться» через MotionPress. **Не добавляй** новой зависимости — если для image-export нужен `html-to-image`, оставь TODO; пока генерация — открытие sheet с превью.
- **AchievementsView**: mosaic-grid 2 колонки. Каждая ачивка — карточка `glass--medium` с `<MorphIcon>` (locked = outline + low opacity, unlocked = filled + full opacity). Long-press → `<LongPressMenu>` (Подробнее / Поделиться). Detail-sheet bottom-sheet с описанием, прогресс-баром, датой получения.
- CSS — `redesign-recap.css`, префиксы `.rh-recap-`, `.rh-share-`, `.rh-ach-`.
- i18n — `redesign.recap.*`.

## Acceptance criteria (отметь все перед финальным push)

- [ ] Home: hero с AmbientStage+KenBurns, quick-grid на морф-иконках, snap-карусели с parallax+dots; mix-views с hero+Play all+Shuffle; Radio с beat-pulse; NotFound лаконичный.
- [ ] Library/Search/Profile/Settings: capsule search с focus-spring; layoutId-индикатор библиотечных табов; long-press menu в плейлистах; ProfileView hero с KenBurns; toggle-anim в Settings + DynamicIsland confirms.
- [ ] Artist/Album/Playlist/Genre/External: sticky-blur header с KenBurns на ArtistView; collage hero на PlaylistView; layoutId-табы на GenreView; бейдж + source attribution на External views.
- [ ] Recap: stories-механика (auto-advance, tap-zones, long-press pause), KenBurns/AmbientStage/BeatPulse на нужных слайдах, outro с CTA «Поделиться»; RecapShareCard рендерится; Achievements — mosaic с морф-иконками и LongPressMenu.
- [ ] reduced-motion корректен на всех экранах.
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.
- [ ] Нет упоминаний внутренних компонентов PrivateCore.

## Workflow

1. После того как foundation появился — `git checkout redesign/ios-2026 && git pull --rebase`.
2. Раздел за разделом, по одному коммиту на смысловой кусок.
3. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Перед финальным коммитом каждой стадии: `npm run build`.
5. Conventional Commits, scope `redesign-c` / `redesign-d` / `redesign-f` / `redesign-h`.
6. На i18n merge-конфликте — оставляй чужие ключи, добавляй свои.
7. Push после каждого коммита.

Когда все четыре стадии завершены и acceptance criteria выполнены — сообщи мне отдельным сообщением «Поток 2 готов».
