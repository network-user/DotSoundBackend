# STAGE-0 — Foundation (последовательно, ПЕРВЫМ)

> Один чат. Не запускать параллельные этапы, пока этот не завершён и не запушен
> в `redesign/ios-2026`.

## Цель

Поставить весь фундамент iOS-редизайна, чтобы потоки A–I могли работать
параллельно, не пересекаясь и не дублируя инфраструктуру:

- зафиксировать ветку и пакет `framer-motion`;
- расширить дизайн-токены (font-stack, large title, dark-only консистентность);
- добавить spring-presets и motion-утилиты;
- ввести Liquid Glass / Ambient / KenBurns / BeatPulse / SwipeRow /
  LongPressMenu / DynamicIsland / MorphIcon / MotionPress / SharedCover как
  готовые primitives, проверенные изолированно;
- предзаложить пустые CSS- и view-файлы под все этапы (A–I) и роуты в App.tsx,
  чтобы остальные этапы их только наполняли;
- предзаложить все нужные иконки в Icon.tsx;
- обновить design-system.md (раздел «Redesign 2026 primitives»).

После Stage-0 `npm run build` обязан быть зелёным; новые primitives
рендерятся (как минимум на /now-playing-stub) без ошибок.

## Owned files

См. SHARED-CONTRACTS.md → раздел «Файлы — Общее (Stage-0 only)» и расширенно:

```
frontend/package.json
frontend/package-lock.json
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/styles/tokens.css
frontend/src/styles/global.css                  # ТОЛЬКО body{font-family}
frontend/src/styles/redesign-shared.css         # NEW
frontend/src/styles/redesign-player.css         # NEW (пустышка)
frontend/src/styles/redesign-nav.css            # NEW (пустышка)
frontend/src/styles/redesign-home.css           # NEW (пустышка)
frontend/src/styles/redesign-library.css        # NEW (пустышка)
frontend/src/styles/redesign-tracks.css         # NEW (пустышка)
frontend/src/styles/redesign-artist.css         # NEW (пустышка)
frontend/src/styles/redesign-recap.css          # NEW (пустышка)
frontend/src/styles/redesign-upload.css         # NEW (пустышка)
frontend/src/components/ui/MotionPress.tsx
frontend/src/components/ui/MorphIcon.tsx
frontend/src/components/ui/SwipeRow.tsx
frontend/src/components/ui/LongPressMenu.tsx
frontend/src/components/ui/DynamicIsland.tsx
frontend/src/components/ui/AmbientStage.tsx
frontend/src/components/ui/KenBurnsCover.tsx
frontend/src/components/ui/BeatPulse.tsx
frontend/src/components/ui/HorizontalSnap.tsx
frontend/src/components/ui/SharedCover.tsx
frontend/src/lib/motion.ts                      # NEW
frontend/src/lib/island.ts                      # NEW
frontend/src/lib/coverPalette.ts                # NEW
frontend/src/lib/haptics.ts                     # NEW (optional but recommended)
frontend/src/components/Icon/Icon.tsx           # +новые иконки
frontend/src/views/NowPlayingView.tsx           # NEW STUB
frontend/src/views/RecapView.tsx                # NEW STUB
frontend/src/locales/i18n_extra2_ru.json        # +каркас redesign.* namespace
frontend/src/locales/i18n_extra2_en.json        # +каркас redesign.* namespace
docs/design-system.md                           # +раздел «Redesign 2026 primitives»
```

## Шаги по порядку

### 0. Ветка

```
git checkout -b redesign/ios-2026 origin/main
```

Если ветка уже создана — `git fetch && git checkout redesign/ios-2026 && git pull`.

### 1. Установка зависимости

```
cd frontend
npm install framer-motion@^11.11.17 --save
```

Зафиксировать `package.json` + `package-lock.json`.

### 2. Расширить `tokens.css`

Добавить в `:root`:

```css
--font-stack-system:
  -apple-system, BlinkMacSystemFont, "SF Pro Text",
  "SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue",
  Arial, "Noto Sans", sans-serif,
  "Apple Color Emoji", "Segoe UI Emoji";

--fs-lt: 34px;   /* large title (Apple) */
--fs-tt: 28px;   /* title 1 */

--ls-display: -0.022em;
--ls-tight:   -0.014em;
--ls-snug:    -0.006em;
```

> Внимание: некоторые токены `--ls-*` уже есть в текущем файле как `0`. Нужно
> аккуратно перезаписать значения, не сломав формат файла.

В `global.css` найти селектор `body` (или создать в самом начале) и поменять
`font-family` на `var(--font-stack-system)`. Никаких других правок в global.css.

### 3. Создать `lib/motion.ts`

```ts
import {
  type Transition,
  type Variants,
  domAnimation,
  LazyMotion,
  m,
  useReducedMotion,
} from 'framer-motion'

export const SPRING_GENTLE: Transition = {
  type: 'spring', stiffness: 220, damping: 28, mass: 0.9,
}
export const SPRING_SNAPPY: Transition = {
  type: 'spring', stiffness: 420, damping: 32, mass: 0.7,
}
export const SPRING_BOUNCY: Transition = {
  type: 'spring', stiffness: 320, damping: 18, mass: 0.85,
}
export const SPRING_LAYOUT: Transition = {
  type: 'spring', stiffness: 260, damping: 30,
}
export const TWEEN_FAST: Transition = {
  type: 'tween', duration: 0.16, ease: [0.22, 0.61, 0.36, 1],
}
export const TWEEN_SLOW: Transition = {
  type: 'tween', duration: 0.36, ease: [0.16, 1, 0.3, 1],
}

export const VARIANTS_FADE_UP: Variants = {
  hidden:  { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: TWEEN_FAST },
}
export const VARIANTS_SCALE_IN: Variants = {
  hidden:  { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: SPRING_GENTLE },
}
export const VARIANTS_PAGE_SLIDE: Variants = {
  hidden:  { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0, transition: SPRING_GENTLE },
  exit:    { opacity: 0, x: -16, transition: TWEEN_FAST },
}
export const VARIANTS_SHEET_SLIDE_UP: Variants = {
  hidden:  { opacity: 0, y: '100%' },
  visible: { opacity: 1, y: 0, transition: SPRING_GENTLE },
  exit:    { opacity: 0, y: '8%', transition: TWEEN_FAST },
}

export { LazyMotion, domAnimation, m, useReducedMotion }
```

### 4. Обернуть приложение `<LazyMotion features={domAnimation}>`

В `main.tsx` (или `App.tsx`) обернуть существующее дерево. Так как `m`-компоненты
тянут только domAnimation features, начальный bundle лёгкий.

### 5. `lib/coverPalette.ts`

Простая реализация:

- `<canvas>` 32×32 downsample;
- частотный гистограмм по `(r>>4, g>>4, b>>4)` 12-bit ключу;
- топ-3 кластера, нормализация в hex;
- кэш `Map<string, CoverPalette>`;
- desaturate до ~30 % saturation, чтобы не нарушить монохром-правило (тон/яркость
  можно, насыщенный цвет — нет).

`extractCoverPalette` возвращает `null` при cross-origin failure и при пустом
URL. Все callers корректно работают с null.

### 6. `lib/island.ts` + `<DynamicIsland>` + `<DynamicIslandHost>`

Стороннего state-менеджера не использовать. Простой in-module store с
`subscribe/notify` + React-хук `useIslandQueue()`. Host рендерится один раз в
`App.tsx`, использует `framer-motion` `AnimatePresence` + `layout`-prop для
shape-shift.

API строго как в SHARED-CONTRACTS. Ровно одна позиция вверху экрана,
с safe-area-inset-top + var(--space-2) отступом.

### 7. Primitives

Реализовать в `components/ui/`:
- `MotionPress.tsx` — `<m.button>` с `whileTap`, `whileHover`, focus ring,
  haptic dispatch.
- `MorphIcon.tsx` — два path map'а (outline/filled) для перечисленных иконок,
  `m.path` с `animate={{ d: target }}` + `m.svg` с `animate={{ fill: ... }}`.
  Если для иконки нет filled-вариaнта — гладко падает на обычный `<Icon>`.
- `SwipeRow.tsx` — `m.div` с `drag="x"`, `dragConstraints={{ left: -160, right: 160 }}`,
  `dragElastic={0.2}`, `onDragEnd` проверяет threshold (~80 px) и вызывает
  `onTrigger`. Подложки экшнов абсолютно позиционированы за основным слоем.
- `LongPressMenu.tsx` — `pointerdown` + `setTimeout(450)`, на trigger открывает
  overlay (`AnimatePresence`), внутри scale-down preview + glass card с пунктами.
- `AmbientStage.tsx` — обёртка `div`, рендерит 3 абсолютных radial-gradient
  слоя. На смене coverUrl — cross-fade через `AnimatePresence`. На
  reduced-motion — статичный последний кадр.
- `KenBurnsCover.tsx` — `<m.img>` с keyframes `scale: [1, 1.06, 1.02, 1.08, 1]`
  и `x/y` шум, бесконечный цикл с длинным duration; на reduced-motion — без
  анимации.
- `BeatPulse.tsx` — `useEffect` + `requestAnimationFrame`, обновляет
  CSS-переменную `--bp-phase` 0..1 на дочернем элементе. Дочерний элемент
  использует `transform: scale(calc(1 + var(--bp-phase) * 0.04))`.
- `HorizontalSnap.tsx` — flex с `scroll-snap-type: x mandatory`, `IntersectionObserver`
  определяет активный индекс, dots снизу, опц. arrows (показывать только при
  hover-capable medium+).
- `SharedCover.tsx` — обёртка над `<img>` с `m.img layoutId={`cover-${id}`}`.

> Каждое primitive — изолированный TSX, экспорт named, без побочных эффектов.

### 8. Дополнить `Icon.tsx`

Один проход добавит:
- `bookmark`, `bookmark-fill`,
- `play-fill`, `pause-fill`, `heart-fill`, `star-fill`, `flame-fill`,
  `home-fill`, `search-fill`, `library-fill`, `chats-fill`, `profile-fill`
  (нужны для MorphIcon-пар);
- `chevron-left`, `chevron-right` (если ещё нет);
- `dots`, `grip`, `add-to-queue`, `headphones`, `wave`, `disc`,
  `chart-bar`, `gear-alt`, `share-arrow`, `airplay-like` (стилизованные
  abstract — без отсылок к real Apple iconography).

`FILLED_ICONS` — пополнить новыми filled-вариантами.

### 9. Stub-вью

Создать минимальные:

```tsx
// frontend/src/views/NowPlayingView.tsx
export function NowPlayingView() {
  return <div className="view view-now-playing-stub">Now Playing</div>
}
```

То же для `RecapView`.

### 10. Обновить App.tsx

Внутри `<AnimatedRoutes>` добавить:

```tsx
const NowPlayingView = lazy(() => import('@/views/NowPlayingView').then(m => ({ default: m.NowPlayingView })))
const RecapView = lazy(() => import('@/views/RecapView').then(m => ({ default: m.RecapView })))
...
<Route path="/now-playing" element={<NowPlayingView />} />
<Route path="/recap" element={<RecapView />} />
```

И смонтировать `<DynamicIslandHost />` внутри `<div id="app">` рядом с
`<OfflineBanner />`. Никаких других правок в App.tsx **в этой и следующих фазах**.

### 11. CSS scaffold

Создать пустые файлы `redesign-<id>.css` с шапкой:

```css
/*
 * redesign-2026 / stage-X
 * Owned by STAGE-X (см. docs/redesign-2026/STAGE-X-...).
 * Не редактировать из других этапов.
 */
```

В `redesign-shared.css` положить:
- класс `.island` (внешний контейнер DynamicIsland, glass-strong + pill);
- класс `.long-press-menu` / `.long-press-overlay` / `.long-press-card`;
- класс `.swipe-row` / `.swipe-action-left` / `.swipe-action-right`;
- класс `.ambient-stage` / `.ambient-layer`;
- класс `.kenburns-cover`;
- класс `.beat-pulse-target` (`will-change: transform`).

В `main.tsx` добавить импорт всех `redesign-*.css` после существующих
`./styles/...` импортов.

### 12. Локализация — каркас

В `i18n_extra2_ru.json` и `i18n_extra2_en.json` добавить (без значений, только
структура, чтобы JSON-файл валидный остался; конкретные ключи добавят сами этапы):

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

Если в файле уже есть содержимое — слить deep-merge'ом, существующее не
перезаписывать.

### 13. design-system.md

В конце файла добавить раздел `## Redesign 2026 primitives` со списком
primitives и кратким API. Не дублировать SHARED-CONTRACTS, ссылаться на него.
Заменить или дополнить раздел про мотион токены, описать SF-стек font-family.

### 14. Smoke-тест

- `npm run build` локально. Должен пройти.
- `npm run dev`, открыть Mini App, проверить:
  - сплэш ок;
  - онбординг/auth открывается;
  - роут `/now-playing` и `/recap` открываются (просто заглушки);
  - DynamicIsland: вызвать `showIsland({ kind: 'toast', title: 'OK' })` из
    DevTools — pill появляется и через 3 с уходит;
  - `MorphIcon` рендерится;
  - reduce-motion: системно включить, открыть страницу, убедиться что
    spring-эффекты выключены.

### 15. Коммит и пуш

Один коммит на весь Stage-0:

```
git add -A
git commit -m "feat(redesign-0): scaffold iOS redesign foundation (motion, primitives, tokens, routes)"
git push -u origin redesign/ios-2026
```

После пуша — **сообщить владельцу**, что Stage-0 готов и можно запускать A–I
параллельно.

## Что НЕ делать в Stage-0

- Не переписывать PlayerBar, BottomNav, HomeView и т. п. — это работа A–I.
- Не удалять старые `Press`, `Sheet`, `GlassSurface` — они нужны до STAGE-Z.
- Не править содержимое `global.css` кроме одной строки font-family.
- Не лезть в `lib/api.ts`, `types/api.ts`, `store/**`.
- Не трогать backend / privatecore / bot / compute-worker.

## Готово, когда

- [ ] `framer-motion` в `package.json`, lock обновлён.
- [ ] Все primitives собираются TypeScript-ом без ошибок.
- [ ] `npm run build` зелёный.
- [ ] DynamicIsland смонтирован в App, рендерится по `showIsland`.
- [ ] Stub-вью `/now-playing` и `/recap` открываются.
- [ ] Все CSS-scaffold файлы созданы, импорт в main.tsx добавлен.
- [ ] `docs/design-system.md` содержит раздел Redesign 2026.
- [ ] Один коммит запушен в `redesign/ios-2026`.
