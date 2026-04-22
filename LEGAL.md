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
