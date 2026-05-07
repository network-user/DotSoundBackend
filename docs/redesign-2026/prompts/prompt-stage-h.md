Ты — агент в чате, отвечаешь за поток H iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Recap (Wrapped) и Achievements

«Wow-фича» проекта. Полноэкранные сториз с большими цифрами, KenBurns на обложках, beat-pulse, share-карточка для социальных сетей. Достижения — мозаичный grid с long-press details.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты: `lib/motion.ts`, `lib/island.ts`, `lib/coverPalette.ts`. Роут `/recap` уже зарегистрирован в `App.tsx` Stage-0.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang. Recap — фирменная страница: можно использовать сильные градиенты монохрома и крупную типографику.

## Обязательно прочитать

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-H-recap.md`
4. `docs/design-system.md`

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром. Фон может быть градиентным но в пределах `--bg-*` и `--surface-*`.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать (KenBurns, beat-pulse, авто-переход slides).
7. PrivateCore-внутренности (метрики, recap-логика — там, она opaque) **не упоминать**. UI получает готовые цифры от API/store.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. Если поля нет — `TODO(redesign-2026)` и mock fallback.
9. Conventional Commits, scope = `redesign-h`.

## Твои файлы

```
frontend/src/views/RecapView.tsx (заменить stub на полную реализацию)
frontend/src/views/AchievementsView.tsx
frontend/src/components/Recap/** (новые компоненты — RecapStorySlide, RecapShareCard и т. п.)
frontend/src/components/Achievements/** (если уже есть)
frontend/src/styles/redesign-recap.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.recap.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.recap.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/** (Stage-A)
frontend/src/components/BottomNav/**, Auth/**, Onboarding/** (Stage-B)
frontend/src/components/TrackCard/**, TrackList/**, TrackCardSheet/** (Stage-E)
frontend/src/views/HomeView, ArtistView, SearchView, ProfileView etc. (Stage-C/D/F)
frontend/src/views/Upload* (Stage-I), admin/** (Stage-G)
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css, остальные redesign-*.css
frontend/src/components/ui/* (Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### RecapView (story-mode)

- Полноэкранная stories-механика: 8–12 слайдов, авто-переход через 5 с (с прогрессбаром-pill наверху).
- Tap left → previous, tap right → next. Long-press на любой части экрана — pause auto-progress.
- Слайды (примерный план — содержимое смотри в API):
  1. Intro: «Твой год в DotSound»
  2. Total minutes listened — большая цифра (`--fs-lt` ×2 или больше) с пульсацией через `m.div animate={{ scale: [1, 1.04, 1] }}`.
  3. Top 3 artists — карусель из больших аватаров через `<HorizontalSnap>`.
  4. Top 5 tracks — стек обложек, каждая через `<KenBurnsCover>` с `<BeatPulse bpm={track.bpm} active>`.
  5. Most played track — full-screen ambient через `<AmbientStage coverUrl={...}>` + KenBurns + beat-pulse.
  6. Top genres — bar-chart из мотион-баров (`m.div animate={{ width: ... }}`).
  7. Mood/time-of-day распределение — горизонтальный гистограм.
  8. Friends/comparison (если есть в API).
  9. Outro/share: large-title, primary CTA «Поделиться» — `<MotionPress variant="primary">`.
- Используй `<AnimatePresence mode="wait">` для смены слайдов (slide-up + crossfade).
- Прогрессбар наверху — пилюлька на каждый слайд, активный заполняется через `m.div animate={{ scaleX: [0, 1] }} transition={{ duration: 5, ease: 'linear' }}`.

### RecapShareCard

- Шерабельная вертикальная карточка 9:16 (формат для stories соцсетей).
- Композиция: коллаж обложек + большие монохромные цифры + DotSound watermark снизу.
- Рендер в DOM (для `html-to-image` / canvas-snapshot — но **не добавляй** новой зависимости; если `html-to-image` ещё нет в `package.json`, оставь TODO для будущей итерации, генерация — пока no-op кнопка которая открывает sheet с превью).
- Кнопки «Сохранить» / «Поделиться» — `<MotionPress>`.

### AchievementsView

- Mosaic-grid 2 колонки.
- Каждая ачивка — карточка `glass--medium` с иконкой `<MorphIcon>` (locked = outline + low opacity, unlocked = filled + full opacity).
- Long-press на ачивку → `<LongPressMenu items=[{ id: 'detail', label: 'Подробнее', onPick: openDetail }, { id: 'share', label: 'Поделиться', onPick: shareAchievement }]>`.
- Detail-sheet (по long-press → Подробнее или по tap) — bottom-sheet с описанием, прогресс-баром (если ачивка с прогрессом), датой получения.

### CSS

Все стили — `frontend/src/styles/redesign-recap.css`. Префиксы: `.rh-recap-`, `.rh-share-`, `.rh-ach-`.

### i18n

Только `i18n_extra2_*.json` под `redesign.recap.*`.

## Acceptance criteria

- [ ] RecapView: stories-механика (auto-advance, tap-zones, long-press pause).
- [ ] Все слайды используют KenBurns, AmbientStage, BeatPulse где это уместно.
- [ ] Outro-слайд имеет CTA «Поделиться» через MotionPress.
- [ ] RecapShareCard рендерится в DOM (даже если фактический image-export — TODO).
- [ ] AchievementsView: mosaic-grid с MorphIcon (filled/outline на locked/unlocked) и LongPressMenu.
- [ ] reduced-motion корректен (KenBurns статичен, beat-pulse выключен, auto-advance выключен — зритель листает вручную).
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на смысловой кусок.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-h`. Примеры:
   - `feat(redesign-h): build cinematic Recap stories with auto-advance`
   - `feat(redesign-h): top-tracks slide with kenburns and beat pulse`
   - `feat(redesign-h): RecapShareCard layout for social export`
   - `feat(redesign-h): AchievementsView mosaic with morph icons and long-press menu`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
