# STAGE-I — Upload & Import

> Параллельный этап. Стартует после Stage-0.

## Цель

Освежить экраны загрузки и импорта в Apple-стиле. Большие drop-zones,
ясные шаги, прогресс через `<DynamicIsland>`, плавные переходы.

## Owned files

```
frontend/src/views/UploadView.tsx
frontend/src/components/Upload/**
frontend/src/components/Import/**
frontend/src/styles/redesign-upload.css
```

## No-touch

Стандарт. `lib/api.ts` — нет (логика Upload — отдельная задача backend/UX).

## Что сделать

### 1. UploadView

- Header с large-title.
- Tabs (file / SoundCloud / Bandcamp / YouTube) — capsule с layoutId-индикатором.
- Активный tab — `<m.div variants={VARIANTS_FADE_UP}>` со staggered появлением
  полей.

### 2. UploadFileTab (drop-zone)

- Большая drop-zone — `glass--medium`, dashed-border (через CSS),
  на dragOver — spring scale up + border highlight через motion.
- При выборе файла — превью карточкой `glass--strong`, метаданные крупно.
- Поля редактирования (title, artist, genre, description, cover) — focus-ring
  spring.
- «Загрузить» — `<MotionPress variant="primary">` + хаптика `medium` на
  старт.
- Прогресс — `showIsland({ kind: 'progress', progress, title: 'Загрузка', ... })`.
- На успехе — `dismissIsland(id)` + `showIsland({ kind: 'toast', title: 'Готово' })`.

### 3. UploadBandcampTab / UploadYouTubeTab / UploadSoundCloudTab

- Те же паттерны: input URL, parse, preview карточкой, Upload-кнопка.
- Прогресс через DynamicIsland.

### 4. Import (ImportSourcePicker / ImportActivityBanner)

- ImportSourcePicker — list с `<MotionPress>` rows + `MorphIcon` per source.
- ImportActivityBanner — заменить на DynamicIsland progress, который держится
  пока импорт идёт.

### 5. Стили

`redesign-upload.css`, префиксы `.ru-up-`, `.ru-im-`.

## Acceptance criteria

- [ ] UploadView tabs со spring layoutId-индикатором.
- [ ] Drop-zone — spring scale-up на dragOver.
- [ ] Прогресс upload — DynamicIsland, не модалки.
- [ ] Import — единый источник прогресса (DynamicIsland).
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-i): rebuild UploadView tabs with spring indicator
feat(redesign-i): drop-zone interactions with motion primitives
feat(redesign-i): unify upload/import progress through DynamicIsland
```
