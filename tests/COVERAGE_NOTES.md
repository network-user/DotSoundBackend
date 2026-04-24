# Cross-repo coverage / test layout (session notes)

## Layout (Phase 0)

- **Backend:** `tests/app/...` mirrors `app/...`; see `AGENTS.md` → «Тесты».
- **PrivateCore:** `tests/dotsound_private_core/...` mirrors `src/dotsound_private_core/...`.
- **Bot:** `tests/bot/...` mirrors `bot/...`.
- **ComputeWorker:** `tests/worker/...` mirrors `worker/...`.

## Approximate coverage (local `poetry run pytest --cov`)

| Repo | Line % (config) | Notes |
|------|-------------------|--------|
| PrivateCore | ~84% with `fail_under=84` and documented `omit` in `pyproject.toml` | Yandex/yt-dlp–heavy modules omitted from gate; see file. |
| Bot | ~93% with `fail_under=80` | |
| ComputeWorker | ~55% total without gate | Demucs omitted; ASR/main not fully exercised in CI. |
| Backend | Not setting `fail_under` (wide suite; some tests may depend on env) | Search/ES tests: `tests/app/search/`, `test_search_query_service.py`, `test_search_index_service.py`, `api/v1/test_search.py`. |

## CI

GitHub Actions enabled in each repo: `lint` + `pytest --cov` + `coverage.xml` artifact where applicable.

## Test fixes (examples)

- **PrivateCore:** `test_yandex_api` moved under `tests/dotsound_private_core/services/`; `test_external_playlist_scanner` / `test_init` aligned with `DownloadError` class name and `__all__`.
- **Backend:** `tests/app/test_config.py` and `test_config_scan_mode.py` — `INTERNAL_API_ALLOWED_CIDRS` / `internal_api_allowed_cidrs` for `DEBUG=false` validator.
