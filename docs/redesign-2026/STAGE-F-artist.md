# STAGE-F — Artist & Author Views

> Параллельный этап. Стартует после Stage-0.

## Цель

Карточка артиста — самое атмосферное место после Now Playing. Большая
обложка, KenBurns, ambient, источники-таб, дискография как карусели,
похожие как горизонтальный slider.

## Owned files

```
frontend/src/components/ArtistView/**
frontend/src/components/AuthorView/AuthorView.tsx
frontend/src/views/ArtistStatsView.tsx
frontend/src/styles/redesign-artist.css
```

## No-touch

Стандарт. `lib/api.ts` / `types/api.ts` / store / Icon — не трогать.

## Что сделать

### 1. ArtistView

- Hero: avatar 200×200 в круге, ambient + KenBurns на подложке-обложке.
  При скролле вниз — параллакс на cover (background-position-y по scroll).
- Под hero — name (large-title), source-switcher chips (`MotionPress`,
  filled на active), monthly-listeners + followers (мелкими меткой).
- «Подписаться» — `<MotionPress variant="primary">` с MorphIcon (`users-following`).
  При нажатии — burst-анимация (filled-state).
- Discography — секции с `<HorizontalSnap>`.
- Similar artists — горизонтальный slider крупных кругов-аватаров с
  каждым по `<MotionPress>` (open artist).
- Avatar-viewer (полный экран по клику) — `m.img layoutId` для shared element.

### 2. AuthorView

- Та же модель, что ArtistView, но скромнее: карточка автора (UGC), его
  треки, кнопки follow / message.

### 3. ArtistStatsView

- Большая KPI-карточка вверху (Monthly listeners), под ней — chart на
  `recharts`. Стилизовать его в монохром — `currentColor`, прозрачные
  линии, тонкие сетки.
- Tooltip с tabular-nums.
- Анимация появления — `VARIANTS_FADE_UP` для каждого блока.

### 4. Стили

`redesign-artist.css`, префикс `.ra-...`.

## Acceptance criteria

- [ ] ArtistView hero — KenBurns + Ambient + параллакс scroll.
- [ ] Source-switcher — морф-иконки + filled state.
- [ ] Follow-button — burst spring + MorphIcon.
- [ ] Discography — snap-карусели.
- [ ] Similar artists — горизонтальный slider кругов.
- [ ] AuthorView — компактная версия паттернов ArtistView.
- [ ] ArtistStatsView — recharts в монохром-стиле + KPI карточка.
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-f): ArtistView hero with ambient, ken burns, source switcher
feat(redesign-f): follow burst, discography carousels, similar artists slider
feat(redesign-f): AuthorView refresh with motion primitives
feat(redesign-f): ArtistStatsView with KPI card and monochrome charts
```
