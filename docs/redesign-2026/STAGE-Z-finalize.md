# STAGE-Z — Finalize (последовательно, ПОСЛЕ всех A–I)

> Один чат. Запускается, когда все A–I залиты в `redesign/ios-2026` и
> владелец считает, что наполнение готово.

## Цель

Сшить редизайн в финальное единое целое: убрать мёртвый legacy CSS, удалить
ставшие ненужными старые primitives (`Press`, `Sheet` если все мигрировали),
сделать сквозной smoke-test, обновить документацию и `TODO.md`, закрыть
все «TODO(redesign-2026)»-метки или переоформить их в backlog, подготовить PR
в `main`.

## Что сделать

### 1. Прогон по всем экранам (smoke)

- Auth → Home → нажать на трек → играет → Player open → Now Playing →
  Lyrics tab → Queue tab → закрыть → Liked → Library → Playlists → Search →
  Artist → Author → Profile → Settings → Recap (?period=week) → Logout.
- Везде reduced-motion включить — проверить отсутствие loop-ов.
- DevTools network throttling slow-3g — посмотреть что DynamicIsland для
  upload progress / WS-reconnect выглядит ок.

### 2. Чистка legacy CSS

Аккуратно, по списку:

- `frontend/src/styles/global.css`:
  - Удалить классы, которых больше никто не использует (rg по проекту).
  - Сохранить классы, что используются в админке и в редизайн-стилях.
- `frontend/src/styles/components.css`: то же самое.
- `frontend/src/styles/animations.css`: оставить минимум общих keyframes,
  специфические перенести в `redesign-*.css`.

ВАЖНО: ни одного класса не удалять без `rg` подтверждения, что он не
используется.

### 3. Удаление дубликатов primitives

- Если все потоки мигрировали с `<Press>` на `<MotionPress>`, удалить
  `frontend/src/components/ui/Press.tsx` (если такой файл есть) и обновить
  импорты.
- То же по `<Sheet>` — если все экраны на `m.div` или новые primitives,
  старый `<Sheet>` можно удалить. Но если в админке или legacy ещё
  используется — оставить.
- `<GlassSurface>` оставить (его primitive универсален).
- `<EmptyState>` / `<SkeletonList>` / `<OfflineBanner>` — оставить (они нейтральны).

### 4. Bundle-size аудит

- `npm run build` → проверить размеры чанков.
- Сравнить с baseline в `scripts/bundle-hygiene-check.mjs`. При необходимости
  обновить пороги (только если реально улучшение/контролируемое
  ухудшение).
- Подтвердить, что `framer-motion` грузится через LazyMotion + domAnimation
  (нет общего `motion` import-а, который тянет полный пакет).

### 5. i18n финал

- Слить `i18n_extra2_*.json` namespace `redesign.*` в основные `ru.json` /
  `en.json` или оставить как есть (зависит от текущей загрузки i18n).
  Решение принять на месте, чтобы не множить файлы. Согласовать с владельцем.

### 6. docs

- `docs/design-system.md`: перевалидировать раздел «Redesign 2026
  primitives». Зафиксировать финальный API всех primitives и токенов.
- `docs/redesign-2026/README.md`: добавить в конец **Status: Released**
  с датой.
- `TODO.md`: новый раздел `## iOS Redesign 2026 (released)` с одной строкой:
  `[x] Полный UI-редизайн фронтенда под iOS/Apple-стиль (Stage 0..Z)`.

### 7. Тесты

- `npm run test` (vitest): зелёный. Если редизайн поломал какие-то
  visual snapshot-тесты — обновить их с осознанием изменений.
- `npm run e2e` (playwright, при наличии запускаемой среды): smoke-сценарии
  не падают.

### 8. PR в main

```
git push origin redesign/ios-2026
gh pr create --base main --head redesign/ios-2026 \
  --title "feat(frontend): iOS UI redesign 2026" \
  --body "..."
```

В body — ссылка на `docs/redesign-2026/README.md` и краткий список ключевых
изменений по этапам.

## Acceptance criteria

- [ ] Smoke по всем главным сценариям проходит.
- [ ] reduced-motion корректен везде.
- [ ] Legacy CSS почищен (без regression).
- [ ] Дубликаты primitives удалены, импорты обновлены.
- [ ] Bundle размер в пределах ожидаемых ~+70 KB gzip к публичному чанку.
- [ ] `npm run build`, `npm run test` — зелёные.
- [ ] `docs/design-system.md`, `TODO.md` обновлены.
- [ ] PR в main создан.

## Коммиты

```
chore(redesign-z): cross-screen smoke and reduced-motion audit
chore(redesign-z): drop legacy CSS and unused primitives
chore(redesign-z): bundle size audit and lazy-motion verification
docs(redesign-z): refresh design-system and todo for iOS redesign 2026
```

И финальный мердж в main делаем после approve владельца.
