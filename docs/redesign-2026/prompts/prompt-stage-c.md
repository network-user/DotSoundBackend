Ты — агент в чате, отвечаешь за поток C iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Home, Discovery, Radio, NotFound

Главный экран должен быть «магнетическим»: большие герои, snap-карусели с parallax, морф-иконки в quick-grid, ambient-цвет на герое. Радио — атмосферная сцена. Жанровые/недельные миксы — ритмичные карусели в Apple Music-стиле.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты в `frontend/src/lib/`: `motion.ts`, `island.ts`, `coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang, референс — iOS 18 + visionOS Liquid Glass + Apple Music.

## Обязательно прочитать перед началом

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-C-home.md`
4. `docs/design-system.md` (раздел Redesign 2026 primitives)

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать (parallax выключать, KenBurns статичен).
7. PrivateCore-внутренности (провайдеры, модели) не упоминать.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. Если поля нет — `TODO(redesign-2026)` + заглушка.
9. `TrackCard` и `TrackList` — это owned files Stage-E, ты их **не правишь**. Можешь их использовать как есть.
10. Conventional Commits, scope = `redesign-c`.

## Твои файлы

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
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.home.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.home.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/components/TrackCard/**, TrackList/** (Stage-E владеет)
frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/** (Stage-A)
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css
frontend/src/components/ui/* (primitives — Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### HomeView v3

- Hero-карточка дня (top): большая обложка, ambient-фон через `<AmbientStage coverUrl={hero.cover_url}>`, KenBurns на cover. Под обложкой — large-title + primary CTA «Слушать» (`MotionPress variant="primary"`).
- Quick-grid на 4–6 ярлыков (Liked, Daily, Weekly, Radio, User-choice, Weekly-top): карточки с `<MorphIcon filled />` + `glass--medium`. Каждый ярлык — `<MotionPress>`.
- Секционные карусели через `<HorizontalSnap parallax pageDots>`: dailyMix, weeklyMix, userChoice, weeklyTop, genre-mixes, followed-artists strip. Каждый item — `<MotionPress>`.
- Followed-artists strip: горизонтальные круги-аватарки.

### DailyMixView / WeeklyMixView / UserChoiceView / WeeklyTopView / GenreMixView

- Header: hero с AmbientStage + KenBurns + большой обложкой.
- TrackList снизу — оборачиваешь существующий `<TrackList>` в `<m.div variants={VARIANTS_FADE_UP} initial="hidden" animate="visible">`. **Внутрь TrackList не лезь.**
- Над TrackList — `Play all` primary button (`MotionPress variant="primary"`) + `Shuffle` secondary (`MotionPress variant="ghost"`). Используй существующие методы PlayerContext/store через хуки (`usePlayerActions`).

### RadioView

- Hero-сцена: вращающийся диск-обложка через KenBurns. BeatPulse в центре.
- Quick-стартеры — 6 «настроений» (chill, focus, gym, cinematic, retro, acoustic) карточками `glass--liquid`. Иконки морф через `<MorphIcon>`.
- Active radio session: большая полноэкранная сцена с AmbientStage от текущей обложки.

### NotFoundView

- Центрированная иллюстрация text-only, large-title, `<MotionPress>` ← «На главную». Лаконично.

### CSS

Все стили — `frontend/src/styles/redesign-home.css`. Префикс классов: `.rh-home-`, `.rh-mix-`, `.rh-radio-`, `.rh-nf-`. Никаких глобальных утилит.

### i18n

Только `i18n_extra2_*.json` под `redesign.home.*`.

## Acceptance criteria

- [ ] Home hero — большой, с AmbientStage + KenBurns.
- [ ] Quick-grid на морф-иконках.
- [ ] Карусели — snap + parallax + dots.
- [ ] Daily/Weekly/User/WeeklyTop/Genre — общий «герой» сверху + Play all / Shuffle.
- [ ] Radio — атмосферная сцена с beat-pulse.
- [ ] NotFound — лаконичный с MotionPress.
- [ ] reduced-motion корректен (KenBurns статичен, parallax выключен, beat pulse выключен).
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на смысловой кусок.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-c`. Примеры:
   - `feat(redesign-c): rebuild HomeView with hero ambient and snap carousels`
   - `feat(redesign-c): polish daily/weekly/user-choice/weekly-top/genre mix views`
   - `feat(redesign-c): atmospheric RadioView with beat pulse hero`
   - `chore(redesign-c): refresh NotFoundView with motion primitives`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
