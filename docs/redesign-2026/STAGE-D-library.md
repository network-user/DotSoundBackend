# STAGE-D — Library, Search, Liked, Playlists, Profile, Settings

> Параллельный этап. Стартует после Stage-0.

## Цель

«Библиотечная» сторона приложения — там, где пользователь живёт после
первой сессии. Должна выглядеть как iOS Music: чистые большие списки,
sticky-headers с blur, шёлковые табы, swipe-actions на rows, профиль —
карточка с большим аватаром и крупными секциями.

## Owned files

```
frontend/src/views/SearchView.tsx
frontend/src/views/LibraryView.tsx
frontend/src/views/LikedView.tsx
frontend/src/views/PlaylistsView.tsx
frontend/src/views/ProfileView.tsx
frontend/src/components/Settings/**
frontend/src/components/Profile/**
frontend/src/styles/redesign-library.css
```

## No-touch

Стандарт. Особо: TrackCard / TrackList — не мой; их редизайнит Stage-E.
Я могу обернуть их в `<SwipeRow>` или `<motion.div>`, но **не править их
внутренности**.

## Что сделать

### 1. Search

- Sticky header с большим search input (capsule, glass-medium). Фокус
  растягивает поле (spring), плейсхолдер плавно сдвигается.
- Под input — chips-фильтры (треки / артисты / альбомы / плейлисты / внешний
  поиск). Активный — filled `MorphIcon`.
- Результаты — секции (треки, артисты, альбомы, плейлисты, внешние).
  Каждая — `m.div variants={VARIANTS_FADE_UP}` со staggered delay.
- Прогрессивная выдача (внешние источники подгружаются после) уже
  работает — её не трогать, только визуальный polish.

### 2. Library

- Капсульные табы вверху (уже есть `.library-tabs`). Заменить на новый компонент
  с `<m.span layoutId="lib-tab-indicator">` под активным.
- Внутри каждой вкладки — список с обёрткой rows в `<SwipeRow>`:
  - Liked: left = «Снять лайк», right = «В очередь».
  - Playlists: left = «В плеер», right = «Удалить» (destructive).
  - Mine: ничего опасного — оставить без swipe или с right = «Поделиться».

### 3. Liked

- Sticky-header с metadata: «N лайков · последний M назад» + sort (newest/oldest/
  по артисту).
- TrackList снизу. Каждый row — `<SwipeRow>`.

### 4. Playlists

- Grid 2-col больших обложек плейлистов. Long-press через `<LongPressMenu>` —
  «Переименовать», «Дублировать», «Удалить».

### 5. Profile

- Hero: большой аватар (128 px), KenBurnsCover на абстрактном градиенте монохрома
  как фон. Имя — large-title.
- Секции (Stats, My tracks, My playlists, Followed artists) — карточки
  `glass--medium`, `MotionPress` для входа.
- Кнопка «Поделиться профилем» — `MotionPress variant="ghost"`.

### 6. Settings

- Sheet (использовать существующий `<Sheet>` для сейф-перехода или новый
  `<m.div drag>` если нужен полноэкранный).
- Каждая секция — карточки с `MotionPress` rows.
- Toggles — `<m.button>` с двух-состоянным `whileTap` (capsule scale on press).
- Haptic на каждое значимое действие (`tick` уже есть).
- Подключить `<DynamicIsland>` для подтверждений сохранения (вместо мелких
  toast'ов).

### 7. Стили

`redesign-library.css`, префиксы `.rd-search-`, `.rd-lib-`, `.rd-liked-`,
`.rd-pl-`, `.rd-profile-`, `.rd-settings-`.

## Acceptance criteria

- [ ] Search input с focus-spring и chips-filter с морф-иконками.
- [ ] Library tabs с layoutId-индикатором.
- [ ] Liked / Playlists rows — со swipe-actions.
- [ ] Long-press на playlist — context-menu.
- [ ] Profile hero — KenBurns на градиентной подложке + большие секции.
- [ ] Settings — гладкие toggle-anim + DynamicIsland подтверждения.
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-d): polish SearchView with capsule input and morph filters
feat(redesign-d): rebuild LibraryView tabs with layout indicator
feat(redesign-d): swipe-actions on Liked and Playlists rows
feat(redesign-d): refresh ProfileView hero with KenBurns avatar bg
feat(redesign-d): settings rebuilt with motion primitives and island confirms
```
