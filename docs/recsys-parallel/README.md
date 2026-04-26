# Recsys: параллельные чаты без конфликтов

## Корни репозиториев (Windows)

| Репо | Путь |
|------|------|
| Backend (хаб, handoff-файлы) | `C:\Users\User\PycharmProjects\DotSoundBackend` |
| PrivateCore | `C:\Users\User\PycharmProjects\DotSoundPrivateCore` |
| ComputeWorker | `C:\Users\User\PycharmProjects\DotSoundComputeWorker` |

Файлы инструкций для чатов (все в Backend):

- `C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\01-track-a-phase1.md`
- `C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\02-track-b-pre-privatecore.md`
- `C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\03-track-b-phase5-backend.md`
- `C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\04-track-b-phase5-worker.md`

План Cursor (вне git): `C:\Users\User\.cursor\plans\recsys_phase_1_+_5_0fd609ec.plan.md`

---

## Порядок запуска (правильный)

### Шаг 0 — подготовка

1. Открой в Cursor workspace **`C:\Users\User\PycharmProjects\DotSoundBackend`** (для чатов A и B1).
2. Для чатов B-pre и B2 переключай root workspace на соответствующий путь из таблицы выше **или** открой второе окно Cursor с другим root.

---

### Шаг 1 — параллельно (максимум два чата)

Запускай **одновременно только эту пару**:

| Чат | Workspace в Cursor | Открой файл-инструкцию | Действие |
|-----|-------------------|-------------------------|----------|
| **A** | `...\DotSoundBackend` | `...\docs\recsys-parallel\01-track-a-phase1.md` | Новый Agent-чат → вставь **промпт** из конца этого файла (или: «выполни всё по этому md»). |
| **B-pre** | `...\DotSoundPrivateCore` | `...\DotSoundBackend\docs\recsys-parallel\02-track-b-pre-privatecore.md` | Второй Agent-чат → промпт из конца `02-...md`. |

**Нельзя** в этом же окне параллелить два чата, оба меняющих **`DotSoundBackend`** на одной ветке (например A и B1).

Дождись: зелёные тесты у A и у B-pre → **merge** PR/ветки A в основную ветку Backend → **merge** B-pre в основную ветку PrivateCore (порядок мержей между собой гибкий, но **B1** ниже требует уже **влитый A** на Backend).

---

### Шаг 2 — только последовательно (после merge A)

| Чат | Workspace | Файл-инструкция | Предусловие |
|-----|-----------|-----------------|-------------|
| **B1** | `...\DotSoundBackend` | `...\docs\recsys-parallel\03-track-b-phase5-backend.md` | В целевой ветке Backend уже **Phase 1 из чата A** (head Alembic ≥ `0059`). Желательно уже влит **B-pre**, если B1 импортирует новые символы из PrivateCore. |

Один чат, один PR на Backend. Тесты и коммит — как в `03-...md`. Затем **merge B1**.

---

### Шаг 3 — после merge B1

| Чат | Workspace | Файл-инструкция | Предусловие |
|-----|-----------|-----------------|-------------|
| **B2** | `...\DotSoundComputeWorker` | `...\DotSoundBackend\docs\recsys-parallel\04-track-b-phase5-worker.md` | В **main** (или базовой ветке воркера) уже есть **смерженный B1**; в начале прочитай контракт API (в конце `03-...md` после реализации или из описания PR B1). |

Один чат на репо Worker. Затем **merge B2**.

---

### Шаг 4 — уборка (после всех мержей A + B-pre + B1 + B2)

См. раздел **«Уборка»** ниже — один финальный коммит в Backend.

---

## Таблица «файл → чат»

| Файл | Чат | Репозиторий | Параллельно с |
|------|-----|-------------|----------------|
| [01-track-a-phase1.md](01-track-a-phase1.md) | **A** | DotSoundBackend | B-pre |
| [02-track-b-pre-privatecore.md](02-track-b-pre-privatecore.md) | **B-pre** | DotSoundPrivateCore | A |
| [03-track-b-phase5-backend.md](03-track-b-phase5-backend.md) | **B1** | DotSoundBackend | — (только после merge A) |
| [04-track-b-phase5-worker.md](04-track-b-phase5-worker.md) | **B2** | DotSoundComputeWorker | после merge B1 |

Исторический контекст: [../../.cursor/rules/context_delete.txt](../../.cursor/rules/context_delete.txt).

---

## Уборка (обязательно в конце спринта)

Когда **все** треки **A**, **B-pre**, **B1**, **B2** влиты в целевые ветки, тесты и ревью пройдены, эти файлы больше не нужны. Исполнитель (агент или ты) в **одном** финальном коммите в `DotSoundBackend`:

1. Удалить **весь каталог** `C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\` (включая этот `README.md` и `01`–`04`).
2. В `C:\Users\User\PycharmProjects\DotSoundBackend\docs\project_context.md` удалить секцию **«Recsys (параллельные чаты / handoff)»** целиком.
3. В `C:\Users\User\PycharmProjects\DotSoundBackend\TODO.md` (и при желании memory) зафиксировать: handoff-файлы recsys удалены, спринт закрыт.

Файл плана Cursor `recsys_phase_1_+_5_0fd609ec.plan.md` при желании удали вручную из `C:\Users\User\.cursor\plans\`.
