# STAGE-H — Wrapped / Recap (новая фича)

> Параллельный этап. Стартует после Stage-0.

## Цель

Новый stories-style раздел `/recap` — «Неделя в DotSound» / «Год в DotSound».
Полноэкранные карточки-сторис, swipe между, autoplay с прогресс-полосой
сверху, музыкальный фон. Это «фишка для возврата» — пользователь раз в
неделю/год получает красивый recap своего слушания.

## Owned files

```
frontend/src/views/RecapView.tsx
frontend/src/components/Recap/**                 (новая папка, любая структура внутри)
frontend/src/styles/redesign-recap.css
```

## No-touch

Стандарт. Особо: `lib/api.ts` — нет. Использовать существующие методы:
- `api.getMyTopTracks` (если есть; если нет — TODO + заглушка)
- `api.getMyStats` / `api.getListenerStats` (если есть)
- Существующие методы из других экранов (followed artists, liked, etc.)

Если данных не хватает — показывать «cтрочки-плейсхолдеры» с пометкой
`TODO(redesign-2026): backend recap endpoint`. Backend-эндпоинт — отдельная
задача за пределами редизайна.

## Что сделать

### 1. RecapView

Полноэкранный контейнер. Параметр `?period=week|year` (default `week`).

Структура:

- Прогресс-полоса вверху (3–8 сегментов, заполняются autoplay-таймером).
- Tap left/right — переход назад/вперёд. Long-press — пауза.
- Swipe-down — выход на предыдущий экран (`navigate(-1)`).
- Crossfade между сторис.
- На каждой сторис — `<AmbientStage>` с обложкой/авторской фотографией,
  large-title, цифра/факт, supportive sublabel.
- На последней сторис — CTA «Поделиться» (генерация share-image через
  canvas — опционально, можно отложить).

### 2. Story cards (внутри Recap)

Реализовать минимум 5 типовых сторис:

1. **Top track**: «Ты слушал X раз — название трека».
2. **Top artist**: KenBurns на аватаре, текст «Любимый артист недели».
3. **Total minutes**: цифра огромная, large-title, скромная подпись.
4. **Genre snapshot**: топ-3 жанра (если есть данные), морф-иконки.
5. **Pinned moment**: «Самый поздний слушаемый трек», или «Первая среда» — что-то «человечное».

Каждая story-карта — отдельный компонент в `components/Recap/`. Например:
- `RecapStoryTopTrack.tsx`
- `RecapStoryTopArtist.tsx`
- `RecapStoryMinutes.tsx`
- `RecapStoryGenres.tsx`
- `RecapStoryPin.tsx`

И общий `RecapStoryShell.tsx` — wrapper с progress-bar, gestures, autoplay
controller.

### 3. Доступ к Recap

В этом этапе:
- Не добавлять отдельную кнопку в HomeView (это работа Stage-C; они уже
  добавили quick-grid и могут потом включить туда recap-карточку
  координированно через TODO).
- Просто работающий деплинк `/recap?period=week` и `/recap?period=year`.

### 4. Стили

`redesign-recap.css`, префикс `.rr-...`. Большие full-bleed экраны без
side-paddings.

## Acceptance criteria

- [ ] `/recap?period=week` открывается, autoplay через сторис работает.
- [ ] Прогресс-сегменты сверху корректно рисуются.
- [ ] Tap left/right, long-press pause, swipe-down close — работают.
- [ ] Минимум 5 типов сторис реализованы.
- [ ] Если данных от api нет — заглушка-слова с `TODO(redesign-2026)`.
- [ ] reduced-motion: autoplay медленнее, без spring, KenBurns статичен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-h): scaffold RecapView with autoplay stories shell
feat(redesign-h): top-track, top-artist, minutes, genres, pin stories
feat(redesign-h): polish ambient backgrounds and gestures
```
