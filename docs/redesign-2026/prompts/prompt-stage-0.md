Ты — агент в чате, отвечаешь за фундаментальный этап iOS-редизайна фронтенда DotSound. Это первый этап в большой работе, после твоего завершения параллельно запустятся 9 других потоков. От качества этого этапа зависит, смогут ли остальные работать без конфликтов.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка для всей работы: `redesign/ios-2026` от свежего `main`. Это монорепо с фронтендом в `frontend/`. Фронт — React 18 + Vite + TypeScript, Telegram Mini App. Уже существуют дизайн-токены, мотион-токены, glass-токены, View Transitions, базовые primitives (Press, Sheet, GlassSurface, EmptyState, SkeletonList).

Владелец принял решения:
- цветовая система — строгий монохром, dark only, без iOS-палитры (правило в `docs/design-system.md`);
- шрифт — system-ui стек (SF Pro на iOS, Roboto на Android), без лицензии;
- анимации — полный `framer-motion`;
- скоп — публичный Mini App + админка (бот, бэкенд, PrivateCore, ComputeWorker не трогаем);
- стратегия — big-bang в одной ветке, без feature-flag;
- референс — iOS 18 база + visionOS Liquid Glass + Now Playing как Apple Music.

## Обязательно прочитать перед началом

В строгом порядке:
1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-0-foundation.md`
4. `AGENTS.md` (ключевые правила репозитория)
5. `docs/design-system.md` (текущая дизайн-система)

## Жёсткие правила (HARD RULES — несоблюдение откатывается)

1. Только `frontend/`. Не трогаешь `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, любые compute-worker.
2. Никаких новых npm-зависимостей кроме `framer-motion@^11.11.17`. Эту ставишь.
3. Палитра — строгий монохром (`--bg/--surface/--text/--accent/--glass-*`). Никаких systemBlue/Pink/Purple, никаких ярких цветов.
4. Тема — dark only.
5. Без эмодзи в UI и в коммитах.
6. Любая loop-анимация и любой spring уважают `prefers-reduced-motion: reduce`.
7. Никаких упоминаний внутренних провайдеров и моделей PrivateCore (ни в коде, ни в комментариях, ни в коммитах). Это публичный фронт.
8. Не правишь `lib/api.ts`, `types/api.ts`, `store/**`. Если нужны новые поля — оставь `TODO(redesign-2026):` коммент и заглушку.
9. Conventional Commits, scope = `redesign-0`.

## Что должен сделать

### 1. Ветка и зависимость

- `git checkout -b redesign/ios-2026 origin/main` (или checkout существующую и pull).
- `cd frontend && npm install framer-motion@^11.11.17 --save`.

### 2. Расширить `frontend/src/styles/tokens.css`

Добавить токены, не ломая существующие:
- `--font-stack-system: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji";`
- `--fs-lt: 34px;` (large title) и `--fs-tt: 28px;` (title 1).
- letter-spacing для крупных заголовков: `--ls-display: -0.022em; --ls-tight: -0.014em; --ls-snug: -0.006em;` (значения в текущем файле обнулены — обнови их).

### 3. В `frontend/src/styles/global.css`

Только одна правка: в селекторе `body` (или там где сейчас задан font-family) поменять значение на `var(--font-stack-system)`. Никаких других правок в этом файле в Stage-0.

### 4. Создать `frontend/src/lib/motion.ts`

Экспортируй:
- `SPRING_GENTLE` (spring stiffness 220, damping 28, mass 0.9), `SPRING_SNAPPY` (420/32/0.7), `SPRING_BOUNCY` (320/18/0.85), `SPRING_LAYOUT` (260/30);
- `TWEEN_FAST` (tween 160 мс ease `[0.22, 0.61, 0.36, 1]`), `TWEEN_SLOW` (tween 360 мс ease `[0.16, 1, 0.3, 1]`);
- варианты `VARIANTS_FADE_UP`, `VARIANTS_SCALE_IN`, `VARIANTS_PAGE_SLIDE`, `VARIANTS_SHEET_SLIDE_UP`;
- реэкспорт `m`, `LazyMotion`, `domAnimation`, `useReducedMotion` из `framer-motion`.

### 5. Создать `frontend/src/lib/island.ts` и `components/ui/DynamicIsland.tsx` + `DynamicIslandHost`

API:
```ts
export interface IslandPayload {
  kind: 'toast' | 'progress' | 'now-playing' | 'error'
  title: string
  hint?: string
  iconName?: string
  progress?: number  // 0..1
  onClick?: () => void
  durationMs?: number
}
export function showIsland(p: IslandPayload): string  // returns id
export function dismissIsland(id?: string): void
```

In-module store с subscribe/notify и React-хук `useIslandQueue`. Host рендерится один раз в `App.tsx`. Внешний контейнер — pill сверху с safe-area-inset-top + var(--space-2) отступом, glass-strong, layout-anim для shape-shift между вариантами.

### 6. Создать `frontend/src/lib/coverPalette.ts`

```ts
export interface CoverPalette {
  tones: [string, string, string]
  text: 'light' | 'dark'
}
export async function extractCoverPalette(url: string): Promise<CoverPalette | null>
```

Реализация: canvas 32×32 downsample, гистограмма по 12-bit ключу, топ-3 кластера. Десатурация до ~30% saturation, чтобы не нарушать монохром. Кэш в Map по URL. На cross-origin/network failure возвращай `null` — все callers это переживают.

### 7. Создать primitives в `frontend/src/components/ui/`

Каждый — отдельный TSX, named export, без побочных эффектов. Используй `m` из `lib/motion`, не прямой `motion`, чтобы LazyMotion работал.

- `MotionPress.tsx` — props: `variant: 'primary' | 'ghost' | 'icon' | 'subtle'`, `haptic`, `onClick`, `disabled`, `ariaLabel`, `className`, `children`. Внутри — `m.button` с `whileTap={{ scale: 0.96 }}` (SPRING_SNAPPY), focus-ring `:focus-visible`, dispatch `haptic(...)` из `lib/telegram` на tap. Под `prefers-reduced-motion` отключи spring.

- `MorphIcon.tsx` — props: `name`, `filled`, `size`. Морфит между outline и filled через `m.path` с `animate={{ d: target }}`. Заранее заведи пары outline/filled для иконок: `heart`, `play`, `pause`, `star`, `bookmark`, `home`, `search`, `library`, `chats`, `profile`, `radio`, `users-following`, `flame`. Если для имени нет filled-варианта — fallback на обычный `<Icon name>`.

- `SwipeRow.tsx` — props: `leftAction?`, `rightAction?` (`{ icon, label, onTrigger, destructive? }`), `children`. Внутри — `m.div` с `drag="x"`, `dragConstraints={{ left: -160, right: 160 }}`, `dragElastic={0.2}`. На threshold ~80 px — haptic + визуальный «приготовился сработать», на release — `onTrigger` или snap-back spring. Подложки экшнов абсолютно позиционированы под основным слоем.

- `LongPressMenu.tsx` — props: `items: { id, label, icon, onPick, destructive? }[]`, `children`. На pointerdown + setTimeout(450) показывает overlay через `AnimatePresence`: blur-backdrop, scale-down preview триггера, glass-карточка с пунктами. Reduced-motion — обычный popover без масштабирования.

- `AmbientStage.tsx` — props: `coverUrl`, `children`, `className`. Извлекает палитру через `extractCoverPalette`, рендерит 3 абсолютных radial-gradient слоя. Cross-fade на смене URL через `AnimatePresence`. Reduced-motion — статика. Дети рендерятся поверх.

- `KenBurnsCover.tsx` — props: `src`, `alt`, `duration?` (default 18). `m.img` с keyframes scale `[1, 1.06, 1.02, 1.08, 1]` + лёгкий x/y шум, бесконечный цикл. Reduced-motion — без анимации, только статичная обложка.

- `BeatPulse.tsx` — props: `bpm` (default 120), `active`, `children`. `useEffect` + `requestAnimationFrame`, обновляет CSS-переменную `--bp-phase` 0..1 на дочернем элементе. Дочерний использует `transform: scale(calc(1 + var(--bp-phase) * 0.04))`. Reduced-motion — без пульсации.

- `HorizontalSnap.tsx` — props: `items`, `renderItem`, `pageDots?`, `showArrows?`, `parallax?`. Flex с `scroll-snap-type: x mandatory`, IntersectionObserver для активного индекса, dots снизу, arrow-controls на ≥md. Parallax — сдвиг внутри карточки от scrollLeft.

- `SharedCover.tsx` — props: `trackId`, `src`, `alt?`, `className?`. Обёртка `m.img` с `layoutId={`cover-${trackId}`}`. Используется и в PlayerBar, и в Now Playing, и в TrackCard.

### 8. Дополнить `frontend/src/components/Icon/Icon.tsx`

Один проход добавь в `PATHS`:
- filled-пары: `heart-fill`, `play-fill`, `pause-fill`, `star-fill`, `bookmark-fill`, `home-fill`, `search-fill`, `library-fill`, `chats-fill`, `profile-fill`, `radio-fill`, `users-following-fill`, `flame-fill`;
- outline `bookmark`, `chevron-left`, `chevron-right` (если ещё нет);
- абстрактные: `dots`, `grip`, `add-to-queue`, `headphones`, `wave`, `disc`, `chart-bar`, `gear-alt`, `share-arrow`, `airplay-like` (нейтральные, без отсылок к real Apple iconography).

Дополни `FILLED_ICONS` Set новыми filled-вариантами.

### 9. Создать stub-вью

- `frontend/src/views/NowPlayingView.tsx` — экспорт named `NowPlayingView`, рендерит `<div className="view view-now-playing-stub">Now Playing</div>`.
- `frontend/src/views/RecapView.tsx` — то же для Recap.

### 10. Обновить `frontend/src/App.tsx`

Внутри текущего `<AnimatedRoutes>` добавь:
```tsx
const NowPlayingView = lazy(() => import('@/views/NowPlayingView').then(m => ({ default: m.NowPlayingView })))
const RecapView = lazy(() => import('@/views/RecapView').then(m => ({ default: m.RecapView })))
```
И роуты `<Route path="/now-playing" element={<NowPlayingView />} />`, `<Route path="/recap" element={<RecapView />} />`.

Смонтируй `<DynamicIslandHost />` рядом с `<OfflineBanner />` в корне `<div id="app">`.

После этого этапа — `App.tsx` больше никто не трогает в фазах A–I.

### 11. CSS scaffold

Создай файлы с шапкой-комментарием (имя владельца):
- `frontend/src/styles/redesign-shared.css` (общие классы для primitives: `.island`, `.long-press-menu`, `.swipe-row`, `.ambient-stage`, `.kenburns-cover`, `.beat-pulse-target` с `will-change: transform`)
- `frontend/src/styles/redesign-player.css` (пустышка для STAGE-A)
- `frontend/src/styles/redesign-nav.css` (пустышка для STAGE-B)
- `frontend/src/styles/redesign-home.css` (STAGE-C)
- `frontend/src/styles/redesign-library.css` (STAGE-D)
- `frontend/src/styles/redesign-tracks.css` (STAGE-E)
- `frontend/src/styles/redesign-artist.css` (STAGE-F)
- `frontend/src/styles/redesign-recap.css` (STAGE-H)
- `frontend/src/styles/redesign-upload.css` (STAGE-I)

В `frontend/src/main.tsx` добавь импорты всех этих CSS после существующих `./styles/...` импортов, и оберни `<App />` в `<LazyMotion features={domAnimation}>`. Это единственная правка `main.tsx` — после неё файл больше никем не трогается.

### 12. i18n каркас

В `frontend/src/locales/i18n_extra2_ru.json` и `i18n_extra2_en.json` добавь (deep-merge с существующим, не перезаписывай):
```json
{
  "redesign": {
    "player":  {},
    "nav":     {},
    "home":    {},
    "library": {},
    "tracks":  {},
    "artist":  {},
    "recap":   {},
    "upload":  {}
  }
}
```

### 13. Документация

В `docs/design-system.md` добавь раздел `## Redesign 2026 primitives` со списком новых primitives и кратким API. Не дублируй SHARED-CONTRACTS — ссылайся.

### 14. Smoke-тест

- `npm run build` локально — должно пройти.
- `npm run dev`, открыть Mini App, проверить: сплэш, /now-playing и /recap stub, DynamicIsland через DevTools `showIsland({kind:'toast', title:'OK'})`, MorphIcon рендерится, reduce-motion отключает spring.

## Что НЕ делать

- Не переписывать PlayerBar / BottomNav / HomeView и т. п. — это работа A–I.
- Не удалять старые `Press`, `Sheet`, `GlassSurface`. Они нужны до STAGE-Z.
- Не трогать содержимое `global.css` кроме одной строки font-family.
- Не лезть в `lib/api.ts`, `types/api.ts`, `store/**`.
- Не трогать backend / privatecore / bot / compute-worker.

## Acceptance criteria (отметь все, прежде чем коммитить)

- [ ] `framer-motion` в `package.json`, lock обновлён.
- [ ] Все primitives собираются TypeScript-ом без ошибок.
- [ ] `npm run build` зелёный (включая `tsc --noEmit`, `bundle-hygiene-check`, `check-admin-bundle`).
- [ ] `DynamicIslandHost` смонтирован в `App.tsx`, рендерится по `showIsland`.
- [ ] Stub-вью `/now-playing` и `/recap` открываются без ошибок.
- [ ] Все CSS-scaffold файлы созданы, импорты в `main.tsx` добавлены, `<LazyMotion>` обёртка стоит.
- [ ] `docs/design-system.md` содержит раздел Redesign 2026.
- [ ] reduced-motion: spring и Ken Burns выключаются.

## Коммит и финал

Один коммит на весь Stage-0:
```
git add -A
git commit -m "feat(redesign-0): scaffold iOS redesign foundation (motion, primitives, tokens, routes)"
git push -u origin redesign/ios-2026
```

После пуша — сообщи мне, что Stage-0 готов и можно стартовать параллельные чаты A–I.
