# STAGE-E — TrackCard, TrackList, TrackCardSheet, Comments, Chat, Legal

> Параллельный этап. Стартует после Stage-0.

## Цель

Все «контентные unit-ы», которые встречаются по всему приложению: карточка
трека, его развёрнутая sheet-карта, комментарии, чат, юридические тексты.
Это пересечение между всеми экранами, поэтому primitives должны быть
аккуратными.

## Owned files

```
frontend/src/components/TrackCard/TrackCard.tsx
frontend/src/components/TrackList/TrackList.tsx
frontend/src/components/TrackCardSheet/**
frontend/src/components/Comments/**
frontend/src/components/Chat/**
frontend/src/views/ChatView.tsx
frontend/src/views/ChatsView.tsx
frontend/src/views/LegalView.tsx
frontend/src/views/LegalDocView.tsx
frontend/src/components/ComplaintModal/**
frontend/src/styles/redesign-tracks.css
```

## No-touch

Стандарт. Особо:
- `lib/api.ts` / `types/api.ts` — нет.
- `App.tsx` — нет (роуты для chat/legal уже есть).
- PlayerContext / LikesContext / store/** — нет.

## Что сделать

### 1. TrackCard

Универсальная карточка трека (используется в карусели, списке, сетке).

- Заменить `<button>` на `<MotionPress>`. Spring scale на tap.
- Cover — `<SharedCover trackId={...}>` чтобы layout-shared с PlayerBar.
- Выделить «играющий» state: лёгкая ambient-glow через `--cover-tone-1` (если
  cover-палитра доступна) + beat-pulse на индикаторе.
- Long-press через `<LongPressMenu>` — items: Like / In queue / Share / Open
  artist / Add to playlist.
- В режиме row (горизонтальный список) добавить опциональный prop
  `swipeable={true}` — обёртка `<SwipeRow>` (left=like, right=queue).

### 2. TrackList

- Виртуализацию не вводим (BREAKING change). Делаем mount-stagger через
  `m.li variants={VARIANTS_FADE_UP}` со staggered children.
- Каждый item — `<TrackCard variant="row" swipeable />`.
- Sticky-header (если есть для сортировки) — `glass--medium`.

### 3. TrackCardSheet

- Открытие через swipe-up из PlayerBar — координирует Stage-A. С нашей
  стороны: убедиться что cover внутри — `<SharedCover trackId>`, чтобы layout
  передавался корректно.
- Sheet-обёртка — оставляем существующую `<Sheet>` пока, но плавно меняем
  внутренности:
  - Action grid (Like / Queue / Share / Album / Artist / More / Lyrics) —
    кнопки на `<MotionPress>` + `<MorphIcon>` (Like, Queue, Share).
  - Edit-pane: переходы между «info / edit» — `m.div` с
    `VARIANTS_FADE_UP` и `AnimatePresence mode="wait"`.
  - LyricsEditor — focus-ring spring; кнопки save/cancel — MotionPress.

### 4. Comments

- CommentSection: input — capsule glass-soft, send-кнопка — MotionPress.
- CommentCard: long-press — context-menu (reply / report / pin / delete).
- Reply branches — `m.div layout` с гладким open/collapse.

### 5. Chat

- ChatBubble: в `bubble-action-bar` — MotionPress + MorphIcon. Quote/Reply
  через motion `layout` для гладкого появления.
- VoicePlayer: spring на play/pause, beat-pulse на воспроизведении.
- VoiceRecorder: кнопка-капсула с pulsing recording-индикатором (через
  CSS keyframes, reduced-motion-aware).
- ChatView header: blur-glass поверх содержимого; back-button
  MotionPress + MorphIcon (chevron-left).
- ChatsView: list rows — `<SwipeRow>` (right=Pin, destructive=Archive).

### 6. Legal

- LegalView: hub-страница в стиле iOS Settings list (rows карточками).
- LegalDocView: длинный текст с sticky table-of-contents (опционально).
  Текст крупный, читабельный (--lh-loose).

### 7. ComplaintModal

- Тот же Sheet, но контент — глядкие переходы между шагами через
  `AnimatePresence mode="wait"`.

### 8. Стили

`redesign-tracks.css`, префиксы `.rt-card-`, `.rt-list-`, `.rt-sheet-`,
`.rt-comment-`, `.rt-chat-`, `.rt-legal-`.

## Acceptance criteria

- [ ] TrackCard — MotionPress + MorphIcon + LongPressMenu.
- [ ] TrackList — staggered появление, swipeable rows.
- [ ] TrackCardSheet — обложка через SharedCover (layout-shared).
- [ ] Comments — long-press context-menu, motion layout reply branches.
- [ ] Chat — все кнопки MotionPress, voice player с beat-pulse.
- [ ] ChatsView — swipe-actions на rows.
- [ ] Legal — list-стиль, читабельный.
- [ ] ComplaintModal — AnimatePresence шаги.
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-e): TrackCard with motion primitives, long-press menu, shared cover
feat(redesign-e): TrackList staggered mount and swipe rows
feat(redesign-e): TrackCardSheet refresh with shared layout cover
feat(redesign-e): Comments and reply branches with motion layout
feat(redesign-e): Chat polish: bubble actions, voice player beat pulse
feat(redesign-e): ChatsView swipe rows and glass header
chore(redesign-e): refresh Legal hub and doc views, ComplaintModal flow
```
