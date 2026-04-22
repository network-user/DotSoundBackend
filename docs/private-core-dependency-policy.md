# DotSoundBackend Private Core Dependency Policy

## Local Development

Use path dependency for fast iteration:

```toml
dotsound-private-core = { path = "../DotSoundPrivateCore", develop = true }
```

The same path-style dependency is also used by `DotSoundBot` and
`DotSoundComputeWorker`. Keep all three checkouts in sibling
directories so editable installs work.

## CI/Production

Pin exact tag or commit:

```toml
dotsound-private-core = { git = "ssh://git@github.com/<owner>/DotSoundPrivateCore.git", tag = "v0.1.0" }
```

## Imported decision modules

The Backend pulls these modules (one import path per file). Each
is a pure-Python decision layer; no I/O or framework code.

| PrivateCore module | Used by Backend code |
|---|---|
| `services.auth_policy` | `app/core/auth.py`, `app/services/auth_service.py` |
| `services.abuse` | `app/services/web_auth_service.py` |
| `services.admin_security_policy` | `app/middlewares/admin_security.py`, `app/services/admin_*.py` |
| `services.web_auth` | `app/services/web_auth_service.py` |
| `services.network_policy` | `app/middlewares/internal_api_allowlist.py`, `app/services/compute_worker_service.py`, `app/services/audio_compute_admin_service.py` |
| `services.asr_policy` | `app/services/lyrics_cascade.py`, `app/services/lyrics_worker.py`, `app/services/compute_router.py`, `app/services/asr_speechkit_adapter.py` |
| `services.compute_anomaly_policy` | `app/services/compute_anomaly_service.py` |
| `services.upload_policy` | `app/services/file_validator.py`, `app/services/upload_service.py` |
| `services.import_rules` | `app/services/import_*` |
| `services.moderation` | `app/services/moderation_service.py` |
| `services.lyrics_provider` | `app/services/lyrics_worker.py` (catalog tier) |
| `services.signal_policy` | `app/services/recommendation_service.py` |

Symbols renamed or removed from PrivateCore must update this
table in the same change.

## Rules

- No floating references to `main` or `master`.
- Every upgrade requires changelog review and contract verification.
- The `ml` extra of PrivateCore (faster-whisper, demucs) is **not**
  installed on the Backend in any environment. The Backend only
  ever uses `generate_lyrics(disable_local_asr=True)` — heavy
  ASR work runs in `DotSoundComputeWorker`.

## Contract: optional fields on `services.lyrics_provider.GenerateResult`

The Backend pulls these attributes off the result object via
`getattr(..., default=None)`, so PrivateCore is free to omit any
of them — older PrivateCore tags will keep working, the new
fields just stay `None` in the Backend payload.

| Field | Type | Backend usage |
|---|---|---|
| `text` | `str` | mandatory — the lyrics text |
| `synced_lines` | `list \| None` | per-line timecodes |
| `sync_quality` | `str \| None` (`"line" / "word" / "none"`) | UI karaoke gating |
| `sync_profile` | `str \| None` (`"cpu_light" / "gpu_full"`) | telemetry |
| `source_name` | `str \| None` | UI attribution for the lyrics text |
| `sync_source_name` | `str \| None` | **(2026-04-22)** UI attribution for the timecodes when they came from a different source than the text (e.g. text from "Yandex Music", sync built locally as "Audio Alignment") |

`sync_source_name` was added so the admin debug panel at the
bottom of every lyrics block can display "Источник текста" and
"Синхронизовал" as two separate labels. Backend stores both in
the `track_lyrics` table (migration `0046_add_lyrics_sync_source_name`).
PrivateCore decides what string to put in each — Backend is a
verbatim adapter.
