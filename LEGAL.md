# DotSound Legal Package

Статус: draft for product and engineering alignment

Этот файл служит индексом юридических документов проекта. Он не
заменяет консультацию с профильным юристом по РФ и не является
самостоятельной публичной офертой без публикации в продукте.

## Документы

- `docs/legal/archive/LEGAL_AUDIT_RU.md` — итоговый юридико-архитектурный
  аудит и матрица рисков (архивный снимок).
- `docs/legal/USER_AGREEMENT.md` — черновик пользовательского
  соглашения / публичной оферты.
- `docs/legal/PRIVACY_POLICY.md` — черновик политики обработки
  персональных данных.
- `docs/legal/COPYRIGHT_POLICY.md` — порядок уведомлений
  правообладателей и takedown flow.
- `docs/legal/UPLOAD_RULES.md` — правила загрузки контента и
  запреты для `UGC`.
- `docs/legal/LEGAL_TEXTS.md` — канонические продуктовые тексты для
  `upload`, `complaints`, `/legal` и карточек треков.
- `docs/legal/SOURCE_TERMS_CHECKLIST.md` — internal checklist для
  проверки Terms/API внешних источников перед публичным запуском.
- `docs/legal/SOUNDCLOUD_TERMS_REVIEW.md` — source-specific internal
  review для текущей SoundCloud integration.

## Backlog: 152-ФЗ и функционал

По мере приближения к публичному запуску — **согласовать** с юристом/ДПО
и при необходимости **изменить** функционал (данные, сроки, внешние
сервисы) под требования к ПДн. Трекер задач: `TODO.md`, раздел
**«Соответствие 152-ФЗ / ПДн»**; контекст для агентов: `AGENTS.md`
(Legal readiness), `docs/project_context.md` (раздел compliance).

## Как использовать

- Для любого изменения в `upload`, `import`, `playback`,
  `complaints`, `recommendation` или `LegalView` сначала проверьте,
  не противоречит ли код этим документам.
- Если UI-текст изменяет юридический смысл, обновите соответствующий
  документ в `docs/legal/` в том же наборе изменений.
- Публикация документов в репозитории полезна для engineering
  alignment, но для реального compliance их нужно отдельно
  опубликовать в продукте и связать с acceptance flow.

## Текущий MVP-риск

На момент создания этого пакета внешний playback через собственный
player DotSound поверх stream URL стороннего сервиса считается
высокорисковой моделью и требует отдельного legal review перед
публичным запуском.

## Cross-border data transfer (Yandex SpeechKit)

Tier `speechkit_paid` в каскаде распознавания лирики передаёт
аудиофайл пользователя в Yandex Cloud (Россия). Это материальное
изменение для пользователя, поэтому tier по умолчанию **выключен**
(`YANDEX_SPEECHKIT_ENABLED=false`).

Перед включением в продакшн обязательно:

1. Раскрыть факт передачи в `docs/legal/PRIVACY_POLICY.md` и
   обновить пользовательское соглашение (`USER_AGREEMENT.md`).
2. Проверить, что для UGC-загрузок есть согласие на обработку
   третьими сторонами (см. чек-лист в `UPLOAD_RULES.md`).
3. Зафиксировать договор с Yandex Cloud (DPA + ToS) в архиве
   `docs/legal/`.
4. Включить kill-switch и месячный бюджет в админ-панели
   (`/admin/audio-compute/speechkit`); по умолчанию бюджет 500 ₽.

Каскад логирует `speechkit_billed` для каждой оплаченной операции;
WorkerAuditLog хранит этот след 90 дней (см.
`app/tasks/audit_log_pruner.py`).
