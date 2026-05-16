# DotSound - TODO Tracker

- [x] **Admin task cancellation hardening (2026-05-16)**
  - Playback repair jobs now receive their `BackgroundJob.id` in the
    Taskiq payload and check both Redis cancel signals and DB
    `cancelling/cancelled` state at safe repair boundaries.
  - Cancellation now stops playback repair before source refresh,
    unresolved suppression, health clearing, and commit where possible,
    while updating live progress with a terminal `cancelled` stage.
  - Bulk active-job cancellation now writes an admin audit-log row with
    actor, filters, matched/cancelled/cancelling counts, purge count, and
    a bounded sample of affected job ids.
  - SoundCloud repair no longer masks total search/refresh transport
    failures as `unresolved`: if every SC search attempt fails, repair
    reports `error` with the upstream reason instead of pretending that
    no replacement exists.
  - Admin-triggered playback repair bypasses the 24h SoundCloud
    no-match Redis cache so a retry after fixing SC search/client-id/proxy
    configuration actually rechecks affected tracks.

- [x] **Mini App PWA precache diet (2026-05-16)**
  - Replaced the broad Workbox precache glob for all Mini App JS/CSS with a
    shell-only whitelist: `index.html`, manifest, startup `index` JS/CSS,
    `vendor`, and base `ru`/`en` locale chunks.
  - Kept icons and notification sounds in the generated precache through
    `includeAssets`, while excluding lazy route/player/admin/HLS chunks from
    service-worker install-time downloads.
  - Added an on-demand `mini-app-lazy-assets` runtime cache for hashed
    non-admin Mini App JS/CSS assets so lazy chunks are cached after first
    real use instead of during initial service-worker install.
  - Verified `frontend` production build with `npm run build`; Workbox
    precache dropped from 101 entries / about 1.64 MiB to 19 entries /
    about 759 KiB.

- [x] **Admin playback repair progress polish (2026-05-16)**
  - Added a playback repair summary endpoint for a concrete bulk run:
    processed/total, status counts, outcome counts, active items, and the
    currently running repair stage.
  - Added human-readable admin labels for playback repair stages in Tasks,
    active jobs, job detail, and the Tracks current-repair panel.
  - Tracks now keeps the latest single/bulk repair run visible with live
    aggregate progress and a direct link to filtered playback repair tasks.
  - Playback repair task details now include a direct action to open the
    affected track card.
  - Decided not to persist full live progress snapshots in DB: Redis remains
    the live source, while `BackgroundJob.result_summary` keeps the final
    durable outcome.
  - Verified targeted admin playback tests, Ruff, and `frontend` production
    build with `npm run build`.

- [x] **Mini App initial payload split for mobile (2026-05-16)**
  - Moved heavy Mini App surfaces behind lazy chunks, including onboarding,
    tutorial, auth, settings, track sheet, profile-adjacent overlays, and
    route-level views that are not required for the first render.
  - Added deferred mounting for player overlays so track card, settings,
    lyrics, queue, equalizer, and complaint chunks are requested only when
    opened while still preserving the existing close animation window.
  - Split screen-specific CSS out of the startup stylesheet and attached it
    to the lazy screens/components that use it: home, artist/album/playlist/
    genre/external pages, upload/import, profile/share UI, edit screens,
    recap/achievements, onboarding/tutorial, and settings legal blocks.
  - Kept shared navigation, player, library, tracks, tokens, global, and
    common component styles in the initial CSS so the shell still renders
    correctly before lazy routes load.
  - Verified `frontend` production build with `npm run build`; the initial
    JS stays around 130 KB and the initial CSS dropped from about 482 KB to
    about 354 KB, with screen CSS emitted as separate lazy assets.

- [x] **Admin active background jobs control (2026-05-16)**
  - Added an admin bulk-cancel endpoint for active `BackgroundJob` rows:
    queued jobs are marked `cancelled`, running/cancelling jobs get a
    cooperative cancel signal and stay visible as `cancelling`.
  - The Taskiq lifecycle middleware now preserves cancelled state on late
    worker completion/error instead of overwriting it with `done` or
    `failed_terminal`.
  - Admin Tasks now has an active background-jobs panel with live stage/log
    data where available, quick detail open, per-job cancel, and a bulk
    cancel action respecting the current task/queue/schedule filters.

- [x] **Proactive SoundCloud playback audit hardening (2026-05-16)**
  - Confirmed the scheduled SoundCloud playback repair sweep audits public
    `third_party_stream` tracks, prioritizing failed/suppressed rows,
    never-checked rows, and then the oldest checked rows.
  - Added regression coverage for healthy proactive checks, failed repair
    suppression, SoundCloud candidate scope, and candidate ordering.
  - Admin Tracks playback-health cells now include last check and repair
    attempt timestamps when available.
  - Reviewed `LEGAL.md` and `docs/legal/` for playback-touching changes;
    no external audio storage, caching, or legal copy model changed.
  - Verified targeted Ruff, repair-worker/metadata tests, admin tracks API
    tests, and `frontend` production build with `npm run build`.
  - Optimized `tests/app/api/v1/admin/test_tracks.py` after re-enabling it:
    admin mutating audit logs now use the test DB, and admin track scenarios
    no longer pay the full upload pipeline; suite passes in ~22s locally.

- [x] **SoundCloud fallback and playback repair live progress (2026-05-16)**
  - SoundCloud stream resolver now tries every available transcoding for
    the selected protocol before failing, so one dead HLS/progressive
    variant no longer blocks playback when another variant works.
  - Admin playback repair enqueue now returns `progress_id` and stores
    live Redis-backed stages for queued, source verification, refresh,
    health clearing, repaired, skipped, unresolved, not found, and error
    outcomes.
  - Admin Tasks background-job details now expose playback repair live
    progress and saved result summaries; the Tracks playback-issues tab
    links directly to the filtered playback repair tasks view.
  - Reviewed `LEGAL.md` and `docs/legal/` for playback-touching changes;
    no media storage/access model or legal copy changed.
  - Verified targeted backend tests, Ruff, and `frontend` production build
    with `npm run build`.

- [x] **Recharts removal and lightweight SVG charts (2026-05-16)**
  - Replaced admin `LineChart`, `Sparkline`, and `AreaChart` components
    with small inline SVG renderers, preserving the existing route APIs.
  - Replaced public `ArtistStatsView` Recharts usage with the same lightweight
    SVG approach for monthly listeners, plays, likes, and followers charts.
  - Removed the `recharts` dependency from the frontend package and deleted
    the now-unused `admin-charts` manual chunk rule.
  - Verified `frontend` production build with `npm run build`; the
    `admin-charts` chunk is gone and large JS chunk warnings remain cleared.

- [x] **Frontend chunk split for mobile payload (2026-05-16)**
  - Switched the HLS loader from the full `hls.js` build to
    `hls.js/light`, keeping the same lazy `loadHlsClass()` entry point.
  - Split the admin app into lazy auth screens, per-route admin chunks,
    and secure admin-only vendor chunks for query/table/charts/QR/fingerprint
    dependencies.
  - Kept admin chunks and admin CSS under `assets/secure/`, filtered them
    from modulepreload, and preserved the admin bundle hygiene checks.
  - Reviewed `LEGAL.md` and `docs/legal/` for the playback-touching HLS
    loader change; no media access, caching, storage, or legal text model
    changed.
  - Verified `frontend` production build with `npm run build`; large JS
    chunk warnings for HLS/admin are gone.

- [x] **Onboarding swipe gesture commit (2026-05-16)**
  - Made the swipe-stage track card start horizontal drag from the whole
    card surface via Framer Motion drag controls.
  - Added right-swipe like and left-swipe dislike commitment with offset
    and velocity thresholds, off-screen card motion, tint/stamp feedback,
    and single haptic feedback per gesture.
  - Kept existing bottom like/dislike/skip buttons and swipe-stage audio
    preview behavior intact.
  - Reviewed `LEGAL.md` and `docs/legal/` for playback/recommendation
    touchpoints; UI gesture only, no media access or recommendation rules
    changed.
  - Verified `frontend` production build with `npm run build`.

- [x] **Admin playback repair idempotency fix (2026-05-16)**
  - Removed the permanent unique constraint from
    `background_jobs.idempotency_key`; duplicate suppression remains the
    Redis TTL guard, so repair can be queued again after the guard window.
  - Added Alembic migration `0103`, service-level enqueue coverage, and
    API-level regression coverage for repeated playback repair after the
    guard window.

- [x] **Mini player card overlay and Media Session polish (2026-05-16)**
  - Bottom `PlayerBar` / touch `MiniPlayerBar` now unmounts while
    `TrackCardSheet` is open, so the track card is not overlapped by the
    mini player.
  - Opening the track card resets local player-bar overflow, playlist, and
    volume popover state so controls do not reappear after closing.
  - Media Session artwork for Android/iOS notification controls now uses
    resized WebP cover variants with correct `sizes` / `type`, and refreshes
    `playbackState` when metadata is rebound.
  - Verified `frontend` production build with `npm run build`.

- [x] **Onboarding genre/artist preview removal (2026-05-16)**
  - Removed standalone play/pause preview buttons from the genre bubble
    step and artist selection step.
  - Removed genre/artist preview queue hooks, hidden preview audio nodes,
    and now-unused preview button styles.
  - Kept genre and artist cards as pure selection controls; the swipe
    track preview flow is unchanged.
  - Verified `frontend` production build with `npm run build`.

- [x] **Mobile mini-player redesign (2026-05-16)**
  - Reworked the touch `MiniPlayerBar` into a floating mobile player
    above the bottom navigation and track sheet layer.
  - Added cover/palette-backed background fill, waveform-style progress,
    and a tighter transport group with play/next plus visible like/menu.
  - Synced touch player layout height tokens for normal, narrow, and
    landscape mobile viewports.
  - Reviewed `LEGAL.md` and `docs/legal/` for playback-touching changes;
    UI-only update, no legal/product text or media access model changed.
  - Verified `frontend` production build with `npm run build` and
    Playwright mobile geometry checks at 390px and 360px.

- [x] **Mini App mobile performance pass (2026-05-16)**
  - `ds-perf-lite` now applies before React render on coarse-pointer,
    low-memory/low-core, save-data, and slow-network devices.
  - Mobile profile disables or simplifies expensive ambient blur,
    Ken Burns, AudioRipple canvas rings, beat scaling, cover reveal
    filters, and high-frequency progress/spectrum updates.
  - Track cards, queue rows, player covers, Home, mix/radio/artist,
    album/playlist, and Now Playing screens now request resized cover
    variants (`w=120/240/480`) with `srcset`/`sizes` where useful.
  - Secondary cover images default to lazy async decoding; the blocking
    Google Fonts import was removed and the Telegram bridge script no
    longer blocks initial HTML parsing.
  - Verified `frontend` production build with `npm run build`; Vite dev
    server is running locally at `http://127.0.0.1:5173/mini_app/`.

- [x] **PWA icon refresh and mobile recommendation reset fix (2026-05-16)**
  - Replaced the install/fav icon source with a minimal monochrome
    `.звук` wordmark and regenerated the PNG PWA assets.
  - Added versioned `icon-v2-*` PWA asset names and switched
    `index.html` + manifest links to them so installed browsers do not
    keep stale icon URLs forever.
  - Recommendation reset no longer hard-reloads the Mini App; after
    successful replay it closes settings and immediately re-enters
    onboarding through an app-level event.
  - App startup now re-checks onboarding status after cookie-session
    restoration, fixing the mobile reload race where reset appeared to
    do nothing.
  - Reviewed `LEGAL.md` and `docs/legal/` for recommendation-touching
    changes; no legal/product text or media access model changed.
  - Verified `frontend` production build with `npm run build`.

- [x] **Admin playback filters and radio skip counters (2026-05-16)**
  - Admin Tracks playback-issues list and filtered ID endpoint now accept
    `playback_error`, matching the latest structured failure detail
    `code` / `reason` from `track_playback_failure_events`.
  - The frontend playback-issues view adds an error code/reason search field;
    bulk selection and repair-all for failure IDs respect the same filter.
  - `radio_auto_skip_exhausted` telemetry now increments Redis daily counters
    by `error_code` / `error_reason`; admin dashboard exposes and renders the
    top radio auto-skip reasons with compact bars.
  - Verified targeted Ruff, admin playback filter tests, signals/stat tests,
    admin dashboard endpoint test, and frontend production build.

- [x] **Proxy pool reliability & observability (2026-05-16)**
  - **IsolateClientAuth**: each `TorCircuit.proxy_url` now includes a unique
    SOCKS5 credential (`socks5://c{N}:dotsound@...`); Tor `SocksPort` entries
    use the `IsolateClientAuth` flag, giving each circuit an independent path
    and genuinely diverse exit IPs within a single Tor process.
  - **NEWNYM callback chain**: `TorPool.register_newnym_callback()` lets any
    module register a callable that runs after NEWNYM. `main.py` registers
    `reset_audio_proxy_clients` so old SOCKS5 tunnels are discarded after
    circuit rotation — new audio streams always open fresh connections.
  - **`reset_audio_proxy_clients()`**: non-closing pool clear; active streams
    keep their existing clients, new requests create fresh ones.
  - **Prometheus metrics**: `tor_circuit_failure_rate{circuit=N}` Gauge +
    `outbound_proxy_pool_size` Gauge; `setup_metrics` registers both in the
    same `CollectorRegistry`. Pool size reported at startup.
  - **`.env.example`**: documents `STREAM_URL_CACHE_TTL_SOUNDCLOUD_HLS` with
    explanation of CDN-signature lifetime (~20 min) and default (1200 s).
  - **Unit tests** (28 passing):
    - `test_proxy_pool.py`: pool reuse, per-proxy identity, closed-client
      recreation, `reset_audio_proxy_clients`, `body_iter` ok/fail/disconnect
      penalty logic, warmup skip when no proxies.
    - `test_tor_pool.py` extended: credential format, uniqueness per index,
      callback registration, sync/async/error-swallowing callbacks.
    - `test_radio_service.py`: suppressed upstream excluded, all-suppressed
      fallback to base, external_link filter in SQL WHERE clause, catalog path.

- [x] **Audio streaming network hardening round 2 (2026-05-16)**
  - `TorCircuit.proxy_url` changed from `socks5://` to `socks5h://` so DNS
    resolution happens inside Tor (prevents DNS leak on the server host).
  - Tor health-check loop now calls `api.ipify.org` instead of
    `api.soundcloud.com`, combining connectivity probe and exit-IP refresh
    in one request; eliminates spurious SC API traffic from monitoring.
  - Added `circuit_proxy_urls()` public method on `TorPool` for warmup use.
  - Added `stream_url_cache_ttl_soundcloud_hls` config field (default 1200 s)
    and use it in `_resolve_stream_via_transcodings` when `protocol_out="hls"`,
    so HLS manifests with short CDN signatures expire before being served stale.
  - Added `_warm_outbound_proxy_pool()` and background task in `lifespan`:
    fires a GET through every static proxy URL (or every Tor circuit) at
    startup, establishing SOCKS5 tunnels ahead of the first user request.
  - `RadioService.build_queue` now filters out suppressed upstream
    (YouTube-mix) tracks via `is_track_playback_suppressed` before merging.
  - `TrackRepository.get_next_tracks` excludes `access_mode='external_link'`
    tracks so reference-only SC entries never appear in radio queues.

- [x] **Audio streaming network hardening (2026-05-15)**
  - SoundCloud streams now prefer HLS by default (`prefer_hls=True`): manifest
    resolution still goes through Tor/proxy, but TS segments are fetched
    directly from the CDN by the client — no more audio bytes through Tor.
  - `_http_proxy_range_get` now uses a pooled `httpx.AsyncClient` per proxy
    URL (keyed dict), so TCP/TLS and SOCKS5 tunnels are reused across
    requests instead of re-negotiated on every audio stream.
  - Fixed client-disconnect false-positive proxy penalty: early stream
    termination (user skips track) no longer marks the circuit as failed;
    only actual upstream `httpx.HTTPError` sets `ok=False`.
  - Tor renewal loop now attempts to reconnect the stem controller when
    `_controller is None` before skipping the NEWNYM signal, so circuits
    are renewed even after a transient controller auth failure at startup.
  - `close_audio_proxy_clients()` added to app shutdown sequence alongside
    `close_sc_http_clients()`.
  - Config comment updated to document `socks5://login:pass@ip:port` format
    for `OUTBOUND_STATIC_PROXY_URLS`.

- [x] **Notification panel portal layering fix (2026-05-15)**
  - In-app notification panel now renders through a document-level portal,
    so sticky/profile headers and other local stacking contexts cannot cover
    the full-screen overlay.
  - Added regression coverage for body-level overlay placement and verified
    the frontend production build.

- [x] **SoundCloud stream diagnostics (2026-05-15)**
  - SoundCloud playback failures now return structured API diagnostics
    in `detail`: stable `code`, `reason`, `stage`, upstream status,
    attempted protocols, retryability, track id, source platform, catalog
    type, and access mode.
  - Frontend API error parsing keeps showing the human `message` when
    backend `detail` is an object, so playback UX remains compatible.
  - Admin Tracks playback-health cells now show the latest structured
    failure `code`, `reason`, `stage`, upstream status, and attempted
    protocols from `track_playback_failure_events`.
  - Radio auto-skip exhaustion telemetry now forwards the latest client
    playback `error_code` and `error_reason`.
  - Verified SoundCloud service regressions, the new playback API
    diagnostics case, admin playback diagnostics, signals API, Ruff, and
    frontend production build.

- [x] **Profile imported track playback and bulk repair (2026-05-15)**
  - Profile “My tracks” cards now pass their list as playback context,
    matching the behavior of the main track lists.
  - Explicit single-track playback clears stale manual/radio/prefetch
    queues, while radio startup preserves its prepared queue.
  - Admin Tracks now supports bulk playback repair enqueueing for selected
    track IDs using the existing per-track background repair worker.
  - SoundCloud import now verifies the stream immediately after import or
    dedup; unresolved imports are marked with playback-health failure
    fields and temporarily suppressed from public feeds until repair.
  - Admin Tracks now includes a one-click action for all current playback
    issues, batching failure and active-suppression IDs through repair.
  - Verified frontend production build and Python syntax compilation.

- [x] **SoundCloud radio playback repair (2026-05-15)**
  - Added same-mode SoundCloud stream-manifest retries through the next
    outbound identity before returning `SoundCloud stream unavailable`.
  - SoundCloud manifest success/failure now feeds outbound/Tor pool health,
    so bad identities are avoided and working ones are reused by pooled
    HTTP clients.
  - Added background playback repair tasks plus a scheduled sweep for
    failed/suppressed SoundCloud third-party streams.
  - Added an admin playback repair action that queues a per-track repair
    job and refreshes stale SoundCloud source URLs when a better match is
    found.
  - Production log review showed the current failures were emitted with
    `proxied=false`, so the deployed backend did not actually use the Tor
    pool/static outbound proxy for those SoundCloud manifest requests.

- [x] **Hard radio auto-skip session cap (2026-05-15)**
  - Radio mode now has a hard 7-track per-session auto-skip cap that does not
    reset on intermediate browser `play` events.
  - After the cap is reached, the player latches radio auto-skip off,
    clears the radio queue, invalidates the current playback session,
    and removes the current audio source to stop stale error callbacks.
  - Verified frontend production build with `npm run build`.

- [x] **Import start Taskiq enqueue race fix (2026-05-15)**
  - Import start now commits `status=importing` before publishing the
    Taskiq worker task, so fast workers no longer skip freshly started
    jobs as `not_found_or_wrong_status`.
  - Telegram and external import skip logs include the actual persisted
    job status to diagnose future queue/state mismatches.

- [x] **Track card artist click target and search state (2026-05-15)**
  - Desktop track cards now make only the rendered artist name clickable,
    not the whole text row beside it.
  - Search state is mirrored into URL params (`q`, `tab`, `genre`), so
    returning from an artist page restores the query and reloads results.
  - Verified frontend production build with `npm run build`.

- [x] **Import provider error diagnostics (2026-05-15)**
  - External import scan failures now keep the source URL and provider
    error message in the job payload for operator/client diagnostics.
  - Import UI and onboarding import modals append safe provider
    `error_code` / `error_message` details to failed scan messages.

- [x] **Import source scan UX and proxy diagnostics (2026-05-15)**
  - Fixed import scanning labels so Yandex/VK/Spotify/SoundCloud scans no
    longer show the Telegram fallback text before the scan job is returned.
  - Preserved Yandex scan failure messages inside the URL modal instead of
    replacing them with a generic modal error.

- [x] **Radio auto-skip exhaustion telemetry (2026-05-15)**
  - Added authenticated client playback telemetry endpoint for the
    `radio_auto_skip_exhausted` event.
  - Backend now exposes the Prometheus counter
    `client_playback_events_total` labelled by event name and surface.
  - Player sends the event when radio auto-skip reaches the safety limit,
    including current track, seed track, skip count, and queue size.
  - Verified signals API tests, Ruff, and frontend production build.

- [x] **Admin filtered ID selection endpoint (2026-05-15)**
  - Added backend admin ID-selection endpoints for tracks and artists so
    `All filtered` selection no longer walks every page from the browser.
  - Tracks support all/list issue/deleted scopes; artists support search,
    enrichment, and catalog-sync filters.
  - Frontend bulk selector now uses one filtered-ID request for all-filtered
    selection and keeps page/range selection as explicit page operations.
  - Verified with Ruff, targeted admin endpoint tests, and frontend build.

- [x] **Radio playback failure guard (2026-05-15)**
  - Radio queues now exclude tracks with active playback suppression or
    recent server-side recovery failure before they reach autoplay.
  - Radio mode stops the client-side auto-skip cascade after a short
    failed burst, avoids server-warming third-party radio streams, and
    prevents Workbox from trying to cache HTTP 206 partial responses.
  - Added 429 backoff for active import polling and stabilized SVG icon
    path swaps that produced invalid intermediate `d` attributes.
  - Verified backend, PrivateCore, frontend prefetch tests, and frontend
    production build.

- [x] **Admin bulk page selection (2026-05-15)**
  - Added shared admin bulk page selector for tracks and artists:
    current page, page range, all filtered pages, and clear selection.
  - Track and artist row selection now persists while moving between
    pages and resets when the active search/filter scope changes.
  - Verified frontend production build with `npm run build`.

- [x] **Genius lyrics Tor fallback and diagnostics (2026-05-15)**
  - PrivateCore lyrics provider now allows direct fallback for Genius
    when optional Tor/proxy identities fail or are quarantined.
  - Genius lookup progress now surfaces safe failure reasons such as
    `HTTP 403` or `OutboundTransportError` in the lyrics panel logs.
  - Verified live lookup for `clout / ДИЛЛЕР` returns Genius text.
  - Added outbound direct-fallback regression coverage.

- [x] **Admin Network outbound request trace fix (2026-05-15)**
  - Backend legacy outbound proxy path now writes request/response
    facts into the outbound status snapshot used by `/network`.
  - SoundCloud, Bandcamp, playback proxy, and audio-compute CDN proxy
    clients are instrumented with service, method, host/path, status,
    duration, transport mode, identity, and cached Tor exit IP.
  - Tor pool now keeps per-circuit `tor:cN` identity and refreshes
    exit IP via each SOCKS port for admin diagnostics.
  - Added regression coverage for outbound metrics hooks and Tor
    circuit observability.

- [x] **Compute worker reverse-proxy IP allowlist fix (2026-05-15)**
  - Internal worker API now resolves `X-Forwarded-For` through trusted
    proxy chains instead of checking the Docker peer IP.
  - Resolved origin IP is reused for global allowlist, per-worker
    allowlist/audit, and worker download token IP binding.
  - `INTERNAL_API_TRUSTED_PROXIES` now inherits `TRUSTED_PROXY_CIDRS`
    when empty; `.env.example` and compute-worker docs describe the
    production setup behind Caddy/nginx.
  - Added regression tests for resolver, middleware, config, and
    worker request IP propagation.

- [x] **Compute worker allowlist and Network tab hardening (2026-05-15)**
  - Compose backend/taskiq services now append the Docker bridge CIDR
    to `INTERNAL_API_ALLOWED_CIDRS`, so local compose compute workers
    from `172.18.x.x` pass the global internal API gate before HMAC
    verification.
  - Admin Network outbound status endpoint now degrades to
    `available=false` instead of returning 500 when the PrivateCore
    outbound snapshot is temporarily unavailable.
  - Network tab UI now shows the backend diagnostic reason for an
    unavailable outbound snapshot.
  - Updated compute-worker docs and covered the status fallback with
    an admin API regression test.

- [x] **Prod memory/storage pressure audit (2026-05-15)**
  - Server snapshot showed no active RAM runaway: Linux page cache kept
    `free` low while `available` stayed about 1.6 GiB; swap pressure is
    real on the 4 GiB host.
  - Root storage pressure was traced primarily to Docker BuildKit cache
    (`docker system df -v`: about 24.8 GiB), not container logs or
    app data.
  - Backend Docker image no longer installs PrivateCore `ml` extra;
    ASR stays in DotSoundComputeWorker/local debug only.
  - Production deploy now prunes Docker build cache with a bounded
    keep-storage default after image prune.
  - Docker SDK admin container probe now closes the client even when
    the Docker socket/list call fails.

- [x] **Lyrics auto-detection, artist resync worker, network admin tab (2026-05-15)**
  - Artist catalog sync now schedules lyrics discovery for every synced
    track, including existing tracks, through the paced global lyrics queue.
  - Auto lyrics detection keeps existing plain text intact; sync runs reuse it
    to build timecodes instead of re-fetching or overwriting the text.
  - Added selected-artists lyrics worker action in admin Artists and a Network
    tab with outbound mode, proxy/Tor status, service counters, and recent
    request traces.

- [x] **Mini player desktop progress visibility fix (2026-05-15)**
  - Restored visible bottom mini-player progress on desktop PlayerBar.
  - Added explicit white played-segment fill and subtle progress background
    tint tied to `--progress` for non-touch `#player-bar`.
  - Verified with `frontend` production build (`npm run build`).


- [x] **Admin startup alert and system load dashboard (2026-05-15)**
  - Backend now sends a best-effort Telegram admin alert after API
    startup completes, using the existing Bot internal admin-alert
    channel and retrying while the bot comes up.
  - Added Redis-backed CPU/RAM/storage resource sampling for the admin
    dashboard, independent of Prometheus availability.
  - Added `/dashboard/system-resources` for current load plus history,
    and rendered CPU/RAM/storage KPIs and charts on the admin dashboard.
  - Documented the new config defaults in `.env.example`.

- [x] **Outbound playback/Tor mode hardening (2026-05-15)**
  - SoundCloud progressive audio proxy now uses the configured outbound
    proxy path for the CDN fetch, not only for stream URL resolution.
  - Taskiq workers now start/stop the same in-process Tor pool lifecycle
    as the API process when `TOR_POOL_ENABLED=true`.
  - Tor pool startup now fails closed by default
    (`TOR_POOL_FAIL_CLOSED=true`) instead of silently falling back to the
    server IP when the pool cannot start.
  - Direct SoundCloud transcoding fallback is disabled by default
    (`SC_STREAM_FALLBACK_DIRECT_ON_TOR_FAILURE=false`), leaving it only
    as an explicit diagnostic escape hatch.
  - Added tests for outbound proxy routing, proxy result feedback,
    config defaults, and SoundCloud direct-fallback behavior.

- [x] **Local audit: admin WS logs and catalog sync tests (2026-05-15)**
  - Fixed admin WebSocket live-log cursor reset: subscribe/filter
    updates no longer reference an out-of-scope `log_since`.
  - Fixed Mini App admin live logs so filters are stored in the WS
    subscription and survive connection open/reconnect timing.
  - Fixed artist catalog sync test mock to return a real background
    job id instead of an `AsyncMock` object.
  - Made compute routing settings cache and lyrics progress snapshots
    degrade gracefully when Redis is unavailable, instead of breaking
    upload/admin track and complaint flows.

- [x] **Admin artists catalog sync UX (2026-05-15)**
  - Admin artists list now uses a dedicated admin endpoint with search
    and pagination.
  - Admin artists list now supports enrichment-state filtering and
    shows catalog sync state directly in the table.
  - Artist catalog resync is queued through tracked background jobs,
    supports bulk admin runs, and reports job ids/errors to the UI.
  - Successful artist enrichment now schedules catalog sync
    automatically so parsed artist data can pull catalog details.
  - Tasks view now supports catalog-sync presets, URL-backed
    background-job filters, status select, and payload target display.
  - Added bulk artist enrichment queueing, catalog-sync filtering in
    Artists, human-readable background-job detail, and Playwright
    coverage for the Artists/Tasks sync workflow.

- [x] **GitHub Actions backend full deploy with observability (2026-05-15)**
  - Backend deploy workflow now checks required SSH secrets before
    invoking `appleboy/ssh-action`.
  - Backend `main` pushes now run
    `OBSERVABILITY=1 ./scripts/deploy.sh full` on the production host.
  - Deploy command timeout raised to 60 minutes for full image rebuilds.

- [x] **Observability prod baseline for admin panel (2026-05-15)**
  - Promtail now attaches Docker Compose `service` labels and parses
    backend JSON `level` labels for Loki queries.
  - Admin log defaults now target the real Compose service name
    `backend` instead of the stale `dotsound-backend` selector.
  - Result: `/api/v1/admin/logs` and live admin WS log tail work
    against the production Docker stack without manual selector fixes.

> Этот файл поддерживается автоматически ИИ-агентом.
> Агент обязан: (1) прочитать этот файл в начале сессии,
> (2) обновить статус после выполнения задач,
> (3) добавить новые задачи если они возникли.

## Статус

- `[ ]` - не начато
- `[~]` - в процессе
- `[x]` - завершено
- `[-]` - отменено / неактуально

- [x] **Импорт Telegram / Yandex: Docker internal API + outbound extras (2026-05-14)**
  — Telegram: backend бьётся в ``BOT_INTERNAL_URL``; бот по умолчанию
  слушал internal API только на ``127.0.0.1`` — из контейнера backend
  connection refused / «All connection attempts failed``. В
  ``docker-compose.yml`` для сервиса ``bot`` заданы
  ``INTERNAL_API_COMPOSE_BIND=true`` и ``INTERNAL_API_HOST=0.0.0.0``
  (порт 8081 не на хосте); в ``.env.example`` и ``PRODUCTION.md``
  задокументированы ``BOT_INTERNAL_URL=http://bot:8081``.
  — (2026-05-15) Валидатор loopback-only в боте ломал старт при
  ``INTERNAL_API_HOST=0.0.0.0`` из compose — добавлен явный
  ``INTERNAL_API_COMPOSE_BIND``.
  — Yandex: образ backend делал ``pip install PrivateCore[ml]`` без
  ``outbound``/``scanners``/``proxies`` — риск неполного outbound-стека;
  Dockerfile ставит ``[ml,outbound,scanners,proxies]``; в
  ``pyproject.toml`` добавлен extra ``outbound`` для path-зависимости.
  В ``PrivateCore/.env.example`` заменена устаревшая подсказка
  ``YANDEX_MUSIC_PROXIES`` на актуальные ``OUTBOUND_*``.
  — Сообщение ``OutboundExhaustedError`` в ``transport.py`` разделено
  на «нет кандидатов» vs «все в карантине».

- [x] **Админ SPA: боковое меню пустое (только дашборд) (2026-05-14)**
  — `AdminProvider` грузил manifest только при `api.getToken()`; при
  cookie-сессии и гонке с `app-auth-ready` токен в памяти мог быть ещё
  `null`, хотя `api.hasSession()` уже true — меню из `useAdminMenu()`
  оставалось пустым. Заменена проверка на `api.hasSession()`.
  — Вход по magic link делал `return` до общего блока init, из-за чего
  не диспатчился `app-auth-ready` (и снова пустое меню). Magic link
  теперь выставляет `authenticated` и не прерывает init; Telegram-auth
  не дёргается, если magic link уже аутентифицировал.

- [x] **Админ: в сайдбаре только «Дашборд» при пустой таблице capabilities (2026-05-14)**
  — Манифест строит меню из строк ``admin_capabilities``; без строк
  остаётся единственный пункт с ``capability: null`` (дашборд).
  — ``ensure_admin_capabilities_for_initialized``: для
  ``is_admin`` + ``admin_init`` и пустого списка грантов — однократная
  выдача всех ``KNOWN_CAPABILITIES``; вызывается из ``build_manifest``
  и ``confirm_admin_init`` (идемпотентно).
  — Дашборд без Prometheus: при пустом ``prometheus_url`` ``query_range``
  возвращает пустую matrix вместо 400.

- [x] **Prod: автозапуск sc_id_refresher (2026-05-14)**
  — `docker-compose.prod.yml` снимает профиль `sc-refresh` с сервиса
  `sc_id_refresher`; `scripts/deploy.sh` добавляет его в `up -d` для
  full / skip-pull / only-backend и в `build` для only-backend.

- [x] **Auth security/cookie regression audit + hardening (2026-05-15)**
  — Backend: в `app/api/v1/auth_email.py` cookie `ds_access` теперь
  выставляется не только в Telegram-ветке, но и в email-логине:
  `/api/v1/auth/email/verify`, `/api/v1/auth/2fa/verify`,
  `/api/v1/auth/2fa/email-fallback/verify`. Это выравнивает поведение
  всех логин-путей с cookie-based session и убирает потерю сессии после
  reload у email-auth пользователей.
  — Backend: `app/core/auth.py` получил graceful fallback на случай
  недоступного Redis в revoke-check/revoke-write (`is_token_revoked`,
  `revoke_token`) — запросы авторизации не падают 500 при сетевых
  сбоях Redis, деградация логируется.
  — Backend: `app/services/admin_auth_service.py` защищён от Redis
  отказов в lockout/step-up read-path (`is_locked_out`,
  `release_lockout`, `consume_step_up`) — админ-логин не падает 500
  при кратковременной недоступности Redis.
  — Tests: добавлены регресс-проверки в
  `tests/app/api/v1/test_auth_email.py` (Set-Cookie для email/2FA
  логина), и в `tests/app/core/test_auth.py` (fallback поведения при
  RedisError).

- [ ] **Убрать временный admin escape hatch в онбординге**
  — На welcome-шаге `OnboardingV2` есть кнопка «Пропустить онбординг
  (admin)», видимая только при `getIsAdmin()`. Нужна, потому что на
  свежем деплое нет треков и swipe-шаг недостижим. Дёргает
  `api.smartSkipOnboarding()`. Когда в каталоге появятся треки
  и любой пользователь сможет закончить онбординг сам — убрать
  блок и его handler в `frontend/src/components/Onboarding/OnboardingV2.tsx`
  (метка `TEMPORARY: admin escape hatch`).

- [x] **Web-логин через Telegram: `?auth=code` в URL для устойчивости (2026-05-14)**
  — `AuthScreen.handleTelegramClick` и `TelegramAuth.handleOpenBot`
  делали только `window.open('https://t.me/<bot>?start=web_login',
  '_blank')` + `setMethod('telegram')` / `setStep('code')` в React-state.
  На мобильных браузерах и при включённом popup blocker `_blank`
  часто открывается в текущей вкладке, либо `t.me` перехватывается
  установленным Telegram-клиентом — итоговая вкладка возвращается
  на `/mini_app/` без `?auth=code` и `AuthScreen` стартует на
  шаге `choose`. Юзер бесконечно жмёт кнопку, поле для ввода кода
  никогда не показывается. Фикс: перед `window.open` пишем
  `?auth=code` в URL через `history.replaceState`. AuthScreen на
  mount читает `params.get('auth') === 'code'` и стартует в
  `method='telegram'` / `step='code'`. На кнопке «Назад» и после
  успешной `verifyTelegramCode` query чистится обратно. Файлы:
  `frontend/src/components/Auth/AuthScreen.tsx`,
  `frontend/src/components/Auth/TelegramAuth.tsx`.

- [x] **Telegram Mini App: онбординг/reset/activation 403 на мобиле (2026-05-14)**
  — После перехода SPA на cookie-based session с double-submit CSRF
  (`b2ace93`) на iOS/Android Telegram WebView cookie `ds_csrf` не
  всегда возвращается в `document.cookie`, хотя `ds_access` ставится
  и автоматически летит в каждый POST. В результате CSRF middleware
  видел cookie-auth, требовал `X-CSRF-Token`, не находил и резал
  любой mutating-запрос 403-кой: `POST /onboarding/activation-event`
  (после auth_success), `POST /onboarding/replay` (кнопка «Сбросить
  рекомендации»), `POST /onboarding/preferences` и т.д. Онбординг
  при этом не появлялся, потому что у уже-онбордившегося user_id=1
  единственный путь его перезапустить — через replay, который
  падал. Лечение: `app/middlewares/csrf.py` пропускает CSRF-проверку
  для запросов с явным `Authorization: Bearer ...` (Bearer нельзя
  выставить кросс-сайтом без CORS-preflight, поэтому cookie-ride
  атака не применима). `frontend/src/lib/activation.ts` отказался
  от `sendBeacon` в пользу `fetch(..., keepalive: true)` с Bearer:
  beacon не умеет ставить заголовки и поэтому всегда уходил без
  auth. `frontend/src/App.tsx` теперь скрывает `<ConsentBanner />`
  пока идёт auth/онбординг/туториал — раньше он накрывал первый
  экран TMA. Тесты: `tests/app/middlewares/test_csrf.py`.

  Параллельно `b2ace93` отключил persisting access-токена в
  `localStorage`, но `frontend/src/lib/chunkedUploader.ts` и
  `frontend/src/lib/pendingEvents.ts` продолжали читать
  `localStorage.getItem('auth-token')` для построения
  `Authorization: Bearer ...`. После коммита они всегда получали
  `null` и POST-запросы уходили без auth: cookie-auth-only ловила
  CSRF middleware (403), а в TMA, где cookie ненадёжна, — сразу
  401. Регрессия ломала загрузку треков (`/tracks/upload/...`) и
  ретраи офлайн-плейкаунтов (IndexedDB-очередь `pendingEvents`).
  Оба места переведены на in-memory токен `api.getToken()`.

- [x] **Прод-инфраструктура: Caddy, мульти-репо CI/CD, deploy script (2026-05-13)**
  — Починен `DotSoundBot/Dockerfile`: editable PrivateCore больше не утекает в
    runtime через `pip freeze` (`--exclude-editable` в builder, `pip install
    --no-deps` для PrivateCore в runtime). `frontend/nginx.conf` теперь
    апгрейдит WebSocket-соединения (`/api/v1/ws*`, `colisten`, admin ws).
    Добавлены `docker-compose.prod.yml` (overlay: убирает публичные порты у
    Postgres/Redis/MinIO/ES/Backend/Frontend, снимает dev bind-mount-ы,
    форсирует `DEBUG=false`) и `Caddyfile` (auto-TLS Let's Encrypt по
    `DOMAIN`/`ACME_EMAIL`; закомментированный блок для `media.*` сабдомена
    под presigned MinIO URL). `scripts/deploy.sh` — идемпотентный CD-скрипт
    с режимами `full / only-backend / only-bot / only-frontend / skip-pull`,
    запускает `alembic upgrade head` через one-shot контейнер.
    GitHub Actions: `deploy.yml` в трёх репо (Backend → only-backend,
    Bot → only-bot, PrivateCore → full). Документация: `docs/deploy/PRODUCTION.md`.
    Makefile: `prod-deploy*`, `prod-logs`, `prod-ps`.

- [x] **Главная: герой — последний прослушанный; «Бесконечная волна» от рекомендаций**
  — В шапке героя приоритет `getListenHistory` (последний уникальный трек),
  затем home highlight, секции и fallback. Подпись героя — `sectionRecent`, если
  источник — история. Кнопка волны на главной берёт сид из порядка секций
  (`continue` → `personalized` → …), не из карточки героя; общая логика с
  пустым состоянием. `HomeView.tsx`.

- [x] **Радио: история «назад» только на 1–2 трека**
  — Локальный `historyRef` в `RadioView` обновлялся только пока смонтирован
  экран `/radio`, поэтому листание с главной/плеера не попадало в стек.
  Хронология сессии (`radioSessionTimeline`, до 30 треков) перенесена в
  `PlayerContext`; назад — `playRadioPrevious` / ветка `playPrev` в радио.
  `RadioView.tsx`, `PlayerContext.tsx`.

- [x] **Настройки: «Сбросить рекомендации» не срабатывало**
  — Баннер согласия (`.consent-banner`) был с `z-index: 1500` и перекрывал
  модалку подтверждения (`z-index: 200`), клики уходили в пустоту. Баннер
  опущен до 166 (выше плеера 165, ниже листов 170+). Базовый `.modal` —
  `var(--z-modal, 220)`. `replayOnboarding`: POST с `Content-Type` и `{}`.
  `ResetRecommendationsSection`: `stopPropagation` на открытии. `global.css`,
  `api.ts`.

- [x] **Онбординг свайп: конец списка — текст и завершение**
  — Флаг `tasteExhausted` после ответа API без новых треков; повторный опрос
  без дублей убран. Плашка с `allDoneHint` в стеке, `canFinish` включает
  исчерпание. `OnboardingV2.tsx`, `onboarding.css`, `i18n_extra2_ru/en.json`.

- [x] **Онбординг свайп-калибровка: play менее навязчив + свайп снова работает**
  — При `prefers-reduced-motion` карточка рендерилась без `drag`, свайпа не было.
  Карточка всегда `m.div` с горизонтальным drag; при reduce — мягче elastic и
  короче exit. Блок `.onb-v2-swipe-card__info` перехватывал указатель — добавлен
  `pointer-events: none`. Неполный свайп: `animate(x, 0)`. После старта
  воспроизведения ~2.2s скрывается центральная кнопка play/pause; пауза — тап
  по карточке (`onTap`). Стили play: ниже непрозрачность, без пульсации.
  `OnboardingV2.tsx`, `onboarding.css`.

- [x] **Онбординг артисты: play под аватаром и не кликался**
  — Та же вложенная кнопка, что у жанров: внешний `<button>` и внутренний
  `role="button"`. Карточка — `div`, выбор — `button.onboarding-artist-card__toggle`,
  превью — отдельный `button.onboarding-artist-preview-btn` с `z-index: 4` и
  позицией `top`/`left` относительно карточки (как раньше угол у 56px-аватара).
  `OnboardingV2.tsx`, `global.css`.

- [x] **Онбординг жанры: превью по play не стартовало**
  — В `usePreviewLoop.start()` первым вызывался `stop()` с `audio.src = ''`,
  что сбрасывает разрешение автовоспроизведения до `await fetcher()` (особенно
  iOS / WebView Telegram). В начале `start()` теперь только `pause` + снятие
  `onended`, без обнуления `src`. В `GenreBubble` убрана вложенная интерактивность
  внутри `<button>` (невалидный DOM): обёртка `div`, выбор жанра и play — два
  соседних `button`, стили `onb-v2-bubble__toggle` в `onboarding.css`.

- [x] **Карточка трека: лайк/дизлайк — белая заливка и синк дизлайков**
  — При входе подгружаются `dislikedIds` через `getDislikedTracks` (раньше
  только лайки). В шите: `MorphIcon` для дизлайка как для сердца; активные
  кнопки `tcs-action-like` / `tcs-action-dislike` с белым текстом и иконкой.
  `LikesContext.tsx`, `MorphIcon.tsx`, `TrackCardSheet.tsx`, `global.css`.

- [x] **Главная: кнопка-«волна» (heroRadio) в монохроме**
  — У `.rh-home-hero__actions .mp-press--ghost` фон и бегущая обводка
  (`::before`, `rh-hero-wave-border`) были цветными (голубой/фиолетовый/бирюза).
  Переведены в белые градиенты: внутренний fill —
  `linear-gradient(135deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.06) 50%,
  rgba(255,255,255,0.14) 100%)`; анимированная обводка — белая, alpha
  0.55→0.18→0.55→0.18. Анимация и форма сохранены, только цвет — белый.
  Точки внизу (`::after`) уже были белыми. `frontend/src/styles/redesign-home.css`.

- [x] **Админ · Треки: три batch-промпта в тулбаре**
  — Раньше одна кнопка «Batch Prompt» (только контекст карточки); lyrics и
  genre/mood были только в overflow. Добавлены отдельные кнопки с счётчиком
  выбранных, overflow — промпты по фильтрам + импорты. i18n en/ru.
  `TracksRoute.tsx`, `locales/en.json`, `locales/ru.json`.

- [x] **Радио: волна-спектр всегда белая**
  — В `RadioView` под диском у `Waveform` стоял `color={accentColor}` из
  палитры обложки, поэтому волна «адаптировалась» в цвет трека. Проп `color`
  убран — компонент сам падает в белый дефолт
  (`rgba(255,255,255,0.88)`/`0.38` для overlay). `AudioRipple` (`ringColor`)
  оставлен на акценте, его пользователь не трогал. `frontend/src/views/RadioView.tsx`.

- [x] **Радио / артист: плавный фон hero (как на главной)**
  — В `.rh-radio-root .rh-radio-hero` и `.rf-artist__hero` за ambient-слоями
  не было подложки, поэтому радиальные «пятна» цвета висели на прозрачном фоне
  и выглядели грязно по краям и за круглой обложкой. Добавлен такой же
  background, как у `.rh-home-hero` (`#0d0d0d` + лёгкий радиальный градиент
  `120% 70% at 50% 0%`), и понижена непрозрачность ambient-слоёв до 0.85,
  как на главной. `frontend/src/styles/redesign-home.css`,
  `frontend/src/styles/redesign-artist.css`.

- [x] **Мини-плеер (touch): два прогресс-бара**
  — В `MiniPlayerBar.tsx` был лишний второй `mp-seek-wrap` с тем же `seekInputRef`;
  нижний слайдер убран, RAF и перемотка снова на одном верхнем seek + `mp-seek-track`.

- [x] **Мини-плеер (touch): seek выше, чёрная подложка, центр метаданных**
  — `--mp-seek-h` 32px, толще видимая полоса; `mp-touch-bottom-fill` (#000);
  `#player-bar` column flex; `tokens.css` `--layout-player-h` для coarse pointer
  синхронизирован с высотой панели.

- [x] **Главная: скелетоны без конца при pull-to-refresh / зависших запросах**
  — При ошибке `getHomeRecommendations` после refresh `sections` оставался
  `null` (вечный скелетон «Продолжить»); catch теперь зеркалит первый mount
  (`setSections([])` + `getTracks` fallback). Watchdog 22s на первый заход:
  сброс `null` → `[]` и попытка fallback. Нормализация `data.sections`.
  Карточка трека: `setLoading(false)` при закрытии до ответа `getTrackCard`.
  `HomeView.tsx`, `TrackCardSheet.tsx`.

- [x] **Радио и карточка трека: волны на мобильных и реакция на звук**
  — На `ds-perf-lite` анализатор больше не отключается (FFT 128 вместо 256);
  в карточке трека волны (`Waveform`) показываются при `isPlaying` даже на телефоне;
  KenBurns + Ambient по-прежнему только без perf-lite. Плашка LIVE в плеере:
  `SpectrumMicroBars` по данным анализатора; при `prefers-reduced-motion` — CSS-полоски.

- [x] **Радио / карточка: круглая рябь вместо «овала»**
  — `KenBurnsCover` `motion="breathe"` (только scale) на диске радио и в карточке;
  `AudioRipple`: квадратный canvas, концентрические кольца, ease + двойной обвод,
  редкие idle-кольца; `.rh-radio-disc-pulse` без translateY, только scale.

- [x] **Карточка трека (touch): радио → экран радио, компактные волны**
  — После успешного `startRadio` при `isCoarsePointer`: `closeCard()` + `navigate('/radio')`.
  Волны: классы `--touch`, ниже/уже область, меньше `Waveform` height/bars; отступы обложка/инфо.

- [x] **Мобильные волны радио: двойной слой, отражение, диск**
  — Два `Waveform` в `.rh-radio-hero-wave-stack`; отражение в
  `.rh-radio-hero-wave-reflect-wrap` (`scaleY(-1)`), основная волна выше,
  отступ `gap` между слоями; фон волн `isolation: isolate`, `z-index: 0`,
  мета `z-index: 5`, диск `z-index: 4`, `touch-action: none` на диске
  (горизонтальный свайд на touch), `pointer-events: none` на фоне волн;
  тап по диску — `togglePlay` при любом треке, свайп — только в
  `radioMode`; `discIsLive` для KenBurns/ripple при `isPlaying`.
  Карточка: обычный `Waveform` на touch (без `radio-tiny`).

- [x] **Мини-плеер: компактные волны радио, прогресс-бар; карточка: обложка без probe**
  — Убран текст LIVE в десктоп-пилле, класс `player-radio-pill--waves-only`; в мини-плеере
  кнопка радио только полоски (`mp-radio-mini`). Слайдер: RAF всегда обновляет `--progress`,
  трек WebKit/Moz с белой заливкой. Статическая обложка в карточке: `re-tcs-cover-static`
  вместо скрывающего `re-tcs-cover-probe`.

- [x] **Плеер: без автоперехода по prefetch после трека вне радио**
  — При естественном `ended` вызывается `playNext({ afterNaturalEnd: true })`;
  ветка `prefetchCacheRef` (рекомендации / `getTrackQueue`) не срабатывает,
  если не `radioMode` (очередь и дозаполнение радио без изменений);
  `onClick={playNext}` заменён на обёртку из‑за сигнатуры с опциями.
  `frontend/src/store/PlayerContext.tsx`, `FullscreenLyrics.tsx`,
  `TrackCardSheet.tsx`.

- [x] **Инициализация: таймауты 12s/25s не сбрасывают авторизацию при живой сессии**
  — Watchdog не вызывает `setNeedsAuth(true)`, если `api.hasSession()`;
  в `finally` инициализации при наличии сессии `setNeedsAuth(false)`
  (гонка с медленным `fetchAndApplyAdminPath` / `syncSessionUserFlags`).
  Chunked upload: `Authorization` из ключа `auth-token`, не `dotsound:token`.
  `frontend/src/App.tsx`, `frontend/src/lib/chunkedUploader.ts`.

---

## Catalog sync / artist page (2026-05-13)

- [x] **Артист: «Похожее: Giza» примешивалось в популярные треки автора**
  — `_sync_one_album_expanded` при синхронизации станции
  (`release_kind = "dotsound_sc_artist_station"`) линковал чужие треки
  на seed-артиста через `TrackArtist`, поэтому `GET /artists/{id}/tracks`
  отдавал песни рекомендованных, а не самого артиста. Теперь для станций
  `link_track(seed)` не вызывается; вместо этого через
  `ArtistService.resolve_and_link(track.id, track.artist)` каждый трек
  станции линкуется к своему настоящему артисту. Тест
  `test_station_sync_does_not_link_foreign_tracks_to_seed` фиксирует
  регрессию. Для очистки уже залитых грязных связей —
  `scripts/cleanup_station_artist_links.py` (dry-run по умолчанию,
  `--apply` для удаления).

---

## Settings sheet UI (2026-05-13)

- [x] **Настройки: видимость профиля через picker, отступы, рекомендации**
  — Профиль для других: `SettingsPickerModal` со stacked-опциями и описаниями;
    между «О приложении» и корзиной — `settings-section-gap--sm`;
    секция рекомендаций: заголовок как у разделов, CTA «Сбросить рекомендации»,
    текст без онбординга, десктоп-диалог по центру с max-width;
    `SettingsPickerModal` `optionLayout`, i18n `i18n_extra_*`.

- [x] **POST `/api/v1/tracks/prefetch` 422 + падение настроек из-за тела запроса**
  — Параметр `body: PrefetchRequest` FastAPI трактовал как query; переименован
    в `payload` + `Body(...)`, убран `from __future__ import annotations` в
    `prefetch.py`; лимит списка через константу + срез по `_effective_prefetch_cap()`
    (в т.ч. при `audio_cache_prefetch_max_ids=0`); тесты
    `tests/app/api/v1/tracks/test_tracks_prefetch_post.py`; фронт: нормализация id
    в `warmTrackStreamCache`, фильтр id в `PrefetchManager`, обёртка
    `spmodal__pill-inner`.

---

## Antivirus integration (2026-05-13)

- [x] **Антивирус: ClamAV интеграция + вкладка в админ-панели**
  — PrivateCore: `CLAMAV_SCAN_TIMEOUT_SECONDS`, `should_reject_on_av_error()` в
    `upload_policy.py`. Backend: модель `ScanEvent`, репозиторий
    `ScanEventRepository`, миграция `0101_scan_events`, расширен
    `scan_service.py` (`log_scan_result`, `get_clamav_status`), DB-логирование
    в `chunked_upload_service.complete()`. Admin API:
    `/admin/antivirus/status`, `/admin/antivirus/stats`,
    `/admin/antivirus/events` с пагинацией/фильтром по вердикту; capability
    `antivirus.view` в manifest. Frontend: `AntivirusRoute.tsx` (статус ClamAV,
    KPI карточки: total/clean/infected/errors/skipped, таблица событий),
    методы `antivirusStatus/Stats/Events` в `adminApi.ts`, маршрут в
    `AdminApp.tsx`, группа ops в `AdminMenu.tsx`.

---

## Mini App / ngrok console (2026-05-12)

- [x] **Telegram Mini App: подсказка «удобнее в браузере» + слайд в Welcome Tutorial**
  — Отложенная карточка (120 с, `z-index` как у install-prompt, над мини-плеером)
    только в Telegram; `localStorage` `ds-tg-browser-hint`: `tutorial` после слайда
    «Браузер», `perm` после «Понятно» / открытия в браузере. Слайд с мокапом PWA /
    уведомлений / блокировки между Mix и Ready. `TelegramBrowserHint`,
    `BrowserPage`, локали `i18n_extra2_*`, стили `components.css` / `onboarding.css`.

- [x] **Дубликаты UGC: hard-delete одного не ломает аудио второго**
  — `AudioBlobService.try_release_for_track`: `FOR UPDATE` на blob,
    учёт соседей с `blob_ref_freed=false` перед удалением S3;
    идемпотентный `attach_playback_blob` (гонка transcode + dedup).
  Тесты: `test_attach_playback_blob_idempotent_when_already_linked`,
  `test_release_reconciles_ref_when_counter_below_sibling_tracks`.

- [x] **Профиль артиста: `track_count` после удаления трека**
  — `GET /artists/{id}` считал через `get_artist_track_ids` без фильтра
  `Track.is_active`; теперь `track_count` = total из
  `ArtistService.list_artist_tracks` (как у `GET .../tracks`).
  `app/api/v1/artists.py`, тесты `test_artist_service.py`.

- [x] **Загрузка файла: галочка правил + API не обходится поддельным `true`**
  — `initUpload` и `FormData` передают реальный `termsAccepted`; шаг 1:
    без галочки нельзя «Дальше» и нельзя submit на превью; тест
    `test_chunked_upload_init_requires_terms_acceptance`. Legacy `/upload`
    и chunked `/upload/init` на бэкенде уже отклоняли `false`.

- [x] **Профиль: блок загрузки; черновик; lyrics sync; успех после upload**
  — `ProfileUploadCallout` перед «Мои треки»; `hasMeaningfulDraft(step>0)`;
  мгновенный `saveDraft` на шагах; восстановление шага после выбора файла;
  `saveLyrics` перед `saveLyricsSync`; успех: `/track/:id` + тост;
  правки `LyricsEditor` / play-кнопка / `ProfileArtistPreview`.

- [x] **Профиль: «Продолжить черновик» и сохранение черновика загрузки**
  — `UploadFileTab` с `key` по `appliedDraft.savedAt` после навигации
    `applyDraft` (иначе state формы не подхватывался); загрузка профиля
    не перезаписывает поля при `initialDraft`; в черновике `audioFileMeta`
    + `hasMeaningfulDraft` (черновик только с выбранным файлом);
    немедленный `saveDraft` при выборе аудио; debounce 250 ms; событие
    `dotsound:upload-draft-changed` + focus/storage/route для каллута.

- [x] **Upload: карточка восстановления черновика на шаге 0**
  — `DraftRestoreCard` под зоной выбора файла (step 0) когда `initialDraft`
    есть и файл ещё не выбран: показывает название/артист/жанр + имя файла
    из `audioFileMeta.name` + подсказку «выберите аудиофайл».
    Кнопка «Сбросить» вызывает `clearDraft` + `onDiscardDraft()` (→ parent
    сбрасывает `appliedDraft`, форма монтируется заново чистой).
    CSS `.ru-up-draft-card`. i18n `redesign.upload.draftCard.*` en/ru.

- [x] **`/admin/manifest` — лавина запросов при 500**
  — `AdminContext`: один `useEffect` с отменой in-flight, без цикла
  `loading`/`failed`; при смене `authTick` манифест перезапрашивается.
- [x] **`listener_stats_service.py` SyntaxError**
  — слитая строка `import structlogfrom` разделена на `import structlog`
  и `from dotsound_private_core...`.
- [x] **PlayerBar: дубликат `PanInfo`**
  — один импорт из `framer-motion`, `npm run build` зелёный.

## MIME detection / Windows (2026-05-12)

- [x] **POST `/api/v1/artists/me/avatar` 500 без libmagic**
  — `file_validator._detect_mime`: при отсутствии `libmagic` (типично
  Windows без рабочего `python-magic-bin`) используются сигнатуры байтов и
  Pillow для JPEG/PNG/WebP. Тесты: `TestMimeFromSignatures`,
  `test_valid_jpeg_when_magic_unavailable`.

## Track covers display (2026-05-12)

- [x] **Карточка трека / лента**: `cover_key` в ответах подставляется из
  варианта группы (если у primary пусто) и с альбома; `GET .../card` и sheet
  подхватывают `cover_url`. Тесты: `test_track_response_build`,
  `test_get_card_falls_back_to_album_cover`.

## Mini App mobile load (2026-05-12)

- [x] **Telegram Mini App: ложный экран «авторизуйтесь» при живой сессии**
  — Watchdog 9 с выставлял `needsAuth` до завершения `authTelegram`; при
  успехе флаг не сбрасывался. Исправлено: `setNeedsAuth(false)` после
  успешного входа (в т.ч. magic link), watchdog 25 с, до 4 с опроса
  `initData` внутри Mini App. `frontend/src/App.tsx`, сборка
  `app/static/mini_app/`.

- [x] **Чёрный экран / долгая «загрузка» в Telegram WebView**
  — Убран warm-boot: мгновенное снятие HTML-лоадера при повторном открытии
  в течение 30 мин отключало и fallback 8 с (`done` уже true), React при
  `!isInitialized` возвращал `null` — оставался пустой `#root` на время
  загрузки бандла/i18n. `frontend/index.html`: без раннего hide, fallback
  120 с. `App.tsx`: splash при инициализации всегда. Скрипт Telegram в head
  до entry (см. также пункт «Мобильный WebView»). Сборка обновляет
  `app/static/mini_app/`.

- [x] **Ускорение холодного старта на телефоне**
  — `hls.js` (~520 KB) только по `import()` при первом HLS (`hlsLoader.ts`,
  `PlayerContext`). `modulepreload` без hls; Workbox precache без
  `assets/hls-*.js` (~−500 KiB precache). i18n: первый кадр после одного
  чанка `ru.json`/`en.json`, три `i18n_extra*` подмешиваются в фоне.

- [x] **Экран ошибки App / daily-mix: кнопка не срабатывала**
  — `app-issue-overlay` z-index ниже части fixed UI (sheets до 10050);
  кнопка через `MotionPress`/portal на touch не доходила. Поднят z-index
  до 10060, нативная `button` + классы `mp-press`. Crash-boundary и
  fallback ленивого маршрута: `window.location.reload()` вместо no-op.

- [x] **Мобильный WebView: «не грузится вообще»**
  — `telegram-web-app.js` снова подключается **синхронно** в head (до entry
  module), плюс `dns-prefetch`/`preconnect` на telegram.org. Регистрация SW
  убрана из HTML (`injectRegister: false`), перенесена в `main.tsx` с
  задержкой ~4 с после `load`, чтобы не конкурировать с первой загрузкой
  JS/CSS. `modulePreload.polyfill: false` (меньше сюрпризов в WKWebView).

## Profile / My Top polish (2026-05-12)

- [x] **«Ваше прослушивание» в профиле: реально за сегодня (UTC), не 30 дней**
  — `period_days=1` не входил в `ALLOWED_PERIOD_DAYS` в PrivateCore,
  бэкенд тихо подменял период на 30. Добавлен день `1`, граница
  `listener_stats_since_utc` (полночь UTC для одного дня), порог
  топа за день — 1 событие. Sparkline в `ListenerStats` берёт 7 дней.
  Тесты: `tests/.../test_listener_stats_policy.py` (PrivateCore).

- [x] **Интерактивные графики «Минуты по дням» + строки жанров/артистов**
  — `ListeningDayChart`: hover (fine pointer) / tap (coarse) с подсветкой
  столбца и строкой деталей; dim остальных. `ProfileStatsTab`: те же
  паттерны для баров жанров и списка артистов + callout с минутами и
  `plays`. `MyTopView`: общий дневной график + интерактивный список жанров.
  Стили в `global.css`, строки `myTop.*` / `profile.stats.*` в локалях.

- [x] **Профиль + «Ваш топ» + экран артиста: UI/UX доводка под монохром**
  — `MyTopView`: добавлена кнопка «назад в профиль», увеличены отступы
  и контейнеризация секций. `ProfileView/global.css`: увеличены отступы
  контента профиля. `ProfileActions` + `redesign-profile.css`: убраны
  цветные иконки, переведено в монохром. `ArtistProfileEditView` +
  `redesign-track-edit.css`: крупная back-кнопка, выровнен CTA, добавлен
  финальный блок действий («Готово» / «Загрузить трек»), прогресс/статусы
  приведены к нейтральной палитре. Backend `artist_service.py`:
  улучшен текст 409-конфликта имени артиста. Тесты:
  `tests/app/api/v1/test_artists_me.py` (новый кейс 409 при занятом имени).

- [x] **Артист: аватар через cover_proxy + CTA загрузки трека**
  — Ключи `artist-avatars/*` не проходили `GET /tracks/cover_proxy`; фронт
  ссылался на несуществующий `/api/v1/files/cover`. Исправлено: префикс в
  `discovery.py`, общий `coverProxyUrl`, обновление `image_key` после POST
  аватара, кнопки «Загрузить трек» на экране редактирования и на своей
  странице артиста, финальный блок текста/кнопок. Тест:
  `test_cover_proxy_accepts_artist_avatars_prefix`.

- [x] **Приватность публичного профиля + QR под тему**
  — Миграция `0100_user_profile_visibility`, `ProfileAccessService`, поля
  `profile_visibility` / `profile_access` в `UserResponse`, 403 на
  stats/tracks/albums/share-card/followers при скрытом или
  «только подписчикам» профиле. Настройки в `SettingsSheet`, `AuthorView`:
  копирование ссылки, модалка QR (`ProfileShareModal`, `initialShowQr`).
  Стили QR в `redesign-profile.css`. Тесты: `test_users.py`, `test_user.py`.
  Плюс: `GET /artists/{id}/share-card`, шаринг артиста в `ArtistView`,
  скруглённый QR (`roundedQr.ts`), карточка + «Копировать»/«QR»/share.

## Mobile player UX (2026-05-12)

- [x] **Свайп трека в карточке + мини-плеер без prev/next на touch**
  — `TrackCardSheet.tsx`: `useSwipeX` на обложке / lyrics / video-spacer;
  кнопки skip-back/skip-forward скрыты при `!desktopFineNav`.
  — `PlayerBar.tsx`: prev/next только при `desktopFineNav`.

- [x] **Фон мини-плеера без стекла**
  — `#player-bar` в `global.css`: непрозрачный тёмный фон, без
  `backdrop-filter`, лёгкая верхняя граница вместо глянца `::before`.

- [x] **Mini App: свайп трека + мини-плеер**
  — `touch-action: pan-y` и вертикальный `drag` Framer на всём баре
  блокировали горизонтальный свайп в WebView: у обложки/NowPlaying/
  TrackCard — `pan-x pan-y`; на touch-баре `drag` отключён, открытие
  полного плеера — тап по «ручке» над скраббером.
  — Убран `#player-bar::after` (подсветка снизу). Класс
  `rp-player-bar--touch`: компактные отступы, обложка 44px, скрыта
  ссылка на внешний источник в баре.

- [x] **Плеер: автосkip недоступных треков**
  — Ошибка загрузки стрима (`playTrack` catch) для любых треков ведёт в
  `skipUnavailableTrack` (раньше `playNext` только SoundCloud + radio).
  — В `audio` `onError` убран дебаунс 500ms после `src` (глушил быстрые
  404); вместо этого игнор только при пустом `currentSrc`/`src`.
  — `playNext` для prefetch/offline якорится на `lastTrackIdRef`, не на
  устаревший `track` из замыкания; `stop`/restore синхронизируют ref.
  — `skipUnavailableTrack` вызывает `playNext({ bypassInFlightGuard: true })`:
  иначе при ошибке `playTrack` внутри обычного `playNext` флаг
  `playNextInFlightRef` блокировал вложенный переход — тосты «пропущено N»
  без смены трека в UI.

- [x] **Анимация смены трека (слайд)**
  — `PlayerContext`: `trackChangeSlide` + инжект направления в `playNext` /
  `playPrev`; `PlayerBar` и `TrackCardSheet`: `AnimatePresence` + spring
  по горизонтали при next/prev, иначе лёгкий fade.

## Playlist improvements (2026-05-12)

- [x] **description в создании/редактировании плейлиста**
  — `PlaylistCreate` / `PlaylistUpdate` получили поле `description`.
  Backend: `playlist_service.create()` / `update()` и `_repo.create()` / `update()`
  передают значение. Frontend: textarea в форме создания и в detail-экране
  `PlaylistsView.tsx`.

- [x] **Поиск публичных плейлистов**
  — `PlaylistRepository.search_public(query, offset, limit)` — WHERE is_public=True
  AND name.ilike. `PlaylistService.search_public()`. Новый endpoint
  `GET /api/v1/playlists/search?q=`. Frontend: debounced-поиск (300 ms)
  в list-экране, показывает чужие публичные плейлисты.

- [x] **UI соавторства плейлистов**
  — Backend: `PlaylistCollabRepository.list_with_users()` + `remove()`.
  `PlaylistService.get_collaborators()` + `remove_collaborator()`.
  Новые endpoints: `GET /playlists/{id}/collaborators`,
  `DELETE /playlists/{id}/collaborators/{user_id}`.
  Frontend: секция соавторов в detail-экране с кнопкой «Пригласить» (копирует
  invite-токен в буфер) и кнопкой удаления каждого соавтора.

- [x] **Fix handleCopyLink**
  — Теперь копирует `{origin}{BASE_URL}#playlist-{id}` вместо `/playlists`.

- [x] **Иконка `user-plus`**
  — Добавлена в `Icon.tsx` (stroke-based, 24×24 viewBox).

- [x] **CSS для новых элементов плейлиста**
  — `redesign-library.css`: стили для `.rd-pl-desc-textarea`,
  `.rd-pl-collab-section/header/row/name/role/empty/loading`,
  `.rd-pl-search-section/loading/empty/results-label`,
  `.rd-pl-desc`, `.rd-pl-create-row`, `.rd-pl-invite-accept-btn`,
  `.rd-pl-invite-input-wrap/actions`, `.loader--sm`.

- [x] **track_count в списке плейлистов**
  — `PlaylistRepository.list_by_owner()` переведён на subquery-паттерн
  (аналогично `list_for_admin`), возвращает `list[tuple[Playlist, int]]`.
  `PlaylistResponse` получил поле `track_count: int = 0`.
  API `list_playlists` заполняет его из subquery-результата.
  Карточки в `PlaylistsView` теперь показывают корректное число треков.

- [x] **Очистка description через PUT**
  — Sentinel `_UNSET` в `playlist_service.py` и `playlist_repository.py`.
  API `update_playlist` проверяет `model_fields_set`: если `description`
  не передан — не трогает поле; если передан пустой/null — очищает.
  Каллеры типа rename (`{name: ...}` без description) не затронуты.

- [x] **Поиск исключает свои плейлисты**
  — `search_public(exclude_owner_id)` в repo и сервисе.
  Endpoint `GET /playlists/search` переключён на `get_optional_user`
  и передаёт `current_user.id` как `exclude_owner_id`.

- [x] **UI принятия инвайта**
  — Кнопка «Принять инвайт» в list-экране (`rd-pl-invite-accept-btn`).
  Модал с инпутом токена → `api.acceptPlaylistInvite()` →
  toast-уведомление и обновление списка плейлистов.
  Ключи i18n: `playlistCollabAccept*` (ru + en).

---

## Playback state persistence (2026-05-12)

- [x] **Fix: listen signal sent for second+ tracks in session**
  — `PlayerContext.tsx`: `listenSignalSentRef.current = false` перемещён в
  `onPlay`, что исправляет баг когда listen-событие для нового трека
  никогда не отправлялось (оно блокировалось `true` оставшимся от
  `sendListenSignal` предыдущего трека).

- [x] **Fix: неверный `duration_listened` при смене трека**
  — `PlayerContext.tsx`: удалён `listenStartTimeRef.current = 0` из
  `playTrack` перед `audio.pause()`. Теперь `duration_listened` считается
  корректно как `currentTime - startTimeRef`, а не `currentTime - 0`.

- [x] **Feat: сохранение позиции при закрытии вкладки**
  — `PlayerContext.tsx`: добавлен `beforeunload` handler — сохраняет
  снапшот в localStorage синхронно перед закрытием вкладки/браузера.

- [x] **Feat: `resume_position_seconds` в ответах API**
  — `app/services/track_response_build.py`: `build_track_response`,
  `build_track_responses`, `dedupe_and_build_track_list` принимают
  `viewer_id: int | None`. При наличии — batch-запрос
  `latest_resume_position` и заполнение поля.
  `app/api/v1/tracks/playback.py` (`GET /tracks/{id}`) и
  `app/api/v1/tracks/discovery.py` (`GET /tracks/`) передают `viewer_id`.
  Результат: поле `resume_position_seconds` теперь приходит при
  одиночном запросе трека и в результатах поиска для авторизованных.

---

## Artist Follows UX (2026-05-12)

- [x] **Онбординг: шаг выбора артистов**
  — `OnboardingV2.tsx`: добавлен шаг `'artists'` между `genres` и `swipe`;
  CSS-классы, API-метод `getOnboardingArtists` и тип `OnboardingArtistItem`
  уже были готовы. `handleGenresSubmit` больше не вызывает
  `saveOnboardingPreferences` — вызов перенесён в `handleArtistsSubmit`
  вместе с реальными `artist_ids`. Результат: при завершении онбординга
  выбранные артисты добавляются как подписки через `follow_artists_bulk`.

- [x] **Слушатели на карточках поиска/дискавера**
  — `app/schemas/artist.py`: `monthly_listeners: int = 0` перенесён
  из `ArtistDetailResponse` в `ArtistResponse` (base).
  `app/repositories/artist_stats.py`: новый метод
  `get_latest_listeners_batch(artist_ids)` — возвращает последний
  снапшот по каждому артисту за один запрос.
  `app/api/v1/recommendations.py`: discover endpoint заполняет
  `monthly_listeners` через batch-запрос.
  Frontend: `ArtistInfo.monthly_listeners?` в `types/api.ts`;
  `search-artist-pill__listeners` в `global.css`; значение
  отображается под именем артиста в поиске.

- [x] **Cron для снапшотов статистики артистов**
  — Миграция `0099_seed_artist_stats_snapshot_job.py`: вставляет запись
  `monthly-artist-stats-snapshot` в `scheduled_jobs` с cron `0 2 1 * *`
  (1-е число каждого месяца 02:00 UTC). Задача:
  `app.services.artist_stats_worker:snapshot_monthly_artist_stats_task`.
  Подхватывается `scheduler_service.py` автоматически.

- [x] **Поиск в шаге артистов онбординга**
  — `ArtistsStep` в `OnboardingV2.tsx`: добавлен `searchQuery` state и
  `filteredArtists = useMemo(...)`. UI-инпут реиспользует существующие
  классы `.onb-v2-genre-search` / `.onb-v2-genre-search__input`.
  Показывает `.onb-v2-artists-empty` если совпадений нет.

- [x] **Таблица по месяцам в ArtistStatsView**
  — `frontend/src/views/ArtistStatsView.tsx`: секция
  `.stats-history-table-section` с таблицей (Месяц / Слушатели /
  Прослушивания / Лайки / Подписчики) добавлена под графиками.
  Данные — те же `sortedHistory`, отсортированные от нового к старому.
  Стили встроены в `ArtistStatsStyles`. i18n ключи добавлены
  в `i18n_extra_en.json` / `i18n_extra_ru.json`.

---

## Цензура текстов (2026-05-12)

- [x] **Глобальная цензура запрещённых слов (RF)**
  — PrivateCore: `services/text_censorship.py` (`censor_text`,
  `contains_banned_content`, `censor_synced_lines`);
  `_BANNED_KEYWORDS` заполнен (~110 форм 4 корневых слов + произв.).
  Backend on-write: `LyricsRepository.create_or_update`,
  `update_sync` (покрывает lyrics_worker); `LyricsService.upsert_translation`;
  `TrackService.update_track`/`admin_update_track` (description);
  `soundcloud_service.py` (description при SC-импорте).
  Backfill: `app/tasks/text_censor_backfill.py` +
  `POST /api/v1/admin/tasks/text-censor-backfill`.
  **Действие:** запустить бэкфилл.

---

## Черновик редактора текстов (2026-05-12)

- [x] **Lyrics editor draft (localStorage autosave)**
  — `frontend/src/lib/lyricsDraft.ts`: per-track ключ
  `dotsound:lyrics-draft:v1:{trackId}`, TTL 24h, три функции
  (save/load/clear). `LyricsEditor.tsx`: флаг `hasUserEdited`,
  дебаунс 800 мс на изменение текста и тайм-кодов, баннер
  восстановления при открытии если черновик отличается от
  сохранённого, очистка черновика после успешного сохранения.
  CSS `.le-draft-banner*` в `global.css`. i18n ключи в
  `i18n_extra_ru.json` / `i18n_extra_en.json`.

---

## Аудит + фиксы (2026-05-11)

- [x] **Security + boundary + logic + perf + frontend pass (1 PR vector)**
  — глубокий аудит всего проекта по запросу пользователя; план в
  `~/.claude/plans/serene-humming-gray.md`. Сделано в 6 логических
  блоках:
  - **Commit 1 (security):** `internal_api_allowlist` теперь читает
    `X-Forwarded-For` только если непосредственный peer входит в
    новый `INTERNAL_API_TRUSTED_PROXIES` allowlist (раньше использовался
    только `request.client.host`); admin `step-up` rate-limit понижен
    с 10/min до 2/min; admin `/backup-code/use` получил
    `@limiter.limit("5/minute")` (раньше без лимита); mock-auth
    endpoint получил runtime-guard `if not settings.debug → 404`
    как defence-in-depth поверх import-time gating.
  - **Commit 2 (security IDOR-проверки):** все три гипотезы агента
    оказались ложными или non-bug — colisten PATCH уже проверяет
    host/dj; playlist invite — это shareable capability token (by
    design); `/users/{id}` уже имеет rate-limit; comment deletion —
    auth-check корректен. Изменений нет.
  - **Commit 3 (public/private boundary):** прямой SQL вынесен из
    `api/v1/recommendations.py` (genre cards) в новый
    `RecommendationRepository.get_genre_cards`; из
    `api/v1/tracks/info.py` (access check x2) в новый
    `TrackRepository.get_access_info`; из `api/v1/admin/audit.py`
    (login history) в `AdminActionLogRepository.list_login_history`.
  - **Commit 4 (logic/soft-delete):** `TrackRepository._playback_listing_allowed`
    теперь AND-ит `Track.deleted_at IS NULL` — фильтр распространяется
    на все list-методы, использующие helper (9 callsite); добавлен
    финальный tie-breaker `TrackComment.id.desc()` в
    cursor-пагинации комментариев.
  - **Commit 5 (performance):** `PlaybackVariantService.resolve_variant_track_ids`
    перешёл с per-platform цикла (≈5-10 SELECT/трек) на единый запрос
    через новый `TrackRepository.find_variants_by_title_and_duration(platforms=[...])`;
    `prefetch` task получил `add_done_callback` с логированием ошибок.
  - **Commit 6 (frontend):** `ws.ts disconnectWS` теперь сбрасывает
    `reconnectDelay` (после logout/relogin WS подключается быстро, а
    не через 30с); `PlayerContext` volume инициализация защищена от
    `NaN` при отсутствующем localStorage; добавлен
    `stopAllLyricsTaskSubscriptions()` в `lyricsTaskStore` и вызван
    из `handleLogout` в `App.tsx`; Onboarding welcome-кнопка
    блокируется при `bootstrapErr`.
  - Помечены ложноположительные: SEC-1/7 (mock-auth уже gated на
    импорте; colisten owner-check уже есть), большая часть FE-2/F-3/F-6/F-9
    (cleanup/try-catch уже на месте).
  - Backend: py_compile зелёный, ruff показал только pre-existing
    annotation ошибки на не-затронутых функциях. Black применён к
    `internal_api_allowlist.py`, `track.py`, `recommendation.py`,
    `recommendations.py`.

## UI Редизайн (2026-05-12)

- [x] **Медиатека: заголовок + быстрый доступ.** `LibraryView`
  получил заголовок «Медиатека» и 4 карточки быстрого доступа
  (Daily Mix, Топ недели, Радио, Мой топ) вместо одиночного Daily Mix.
  CSS-класс `rd-lib-shortcuts` (сетка 2×2).

- [x] **Поиск треков в плейлист: новый `TrackPickerSheet`.**
  Заменил инлайн-пикер в `PlaylistsView` (старый: пагинация из
  `api.getTracks` + `api.getMyLibrary`, без обложек, путаная UX) на
  `TrackPickerSheet` — полноценный Sheet с `searchSuggest`-поиском,
  обложками 40×40, секцией «Из понравившихся» по умолчанию.
  Убраны ~100 строк состояния/логики из PlaylistsView.

- [x] **Свайп трека на мобиле: `useSwipeX`.** Новый хук
  `hooks/useSwipeX.ts` детектирует горизонтальный свайп через
  pointer-events (threshold 60px, ratio 1.5×). Применён к обложке
  в `NowPlayingView` (порог 72px) и к обложке в `PlayerBar` (56px).
  Только на мобильных (!desktopFinePointer). Свайп влево → playNext,
  вправо → playPrev. Haptic feedback.

### Follow-up (вынести отдельным PR)

- [x] **Admin ORM cleanup B-3-tail:** `app/api/v1/admin/tasks.py`
  ≈30 точек прямого SQL вынесены в новый
  `app/repositories/admin_tasks.py` (`AdminTasksRepository`).
  Все 14 хендлеров теперь не содержат `select()`, `session.execute()`
  или `session.get()`. Внутренние модели остаются только для
  серилизаторов и factory (ScheduledJob ctor) — это разрешено.
- [ ] **P-3 recommendations build batching:** сейчас секции в
  `/recommendations/home` собираются последовательно (loop по
  sections с `dedupe_and_build_track_list` на каждой). Можно
  объединить в один build-pass — но требует snapshot-теста на
  состав/порядок ответа до рефактора.
- [-] **F-2/F-3/F-11 frontend race (false positive на bug-severity):**
  при второй проверке закрытое `let cancelled = false` в каждом
  effect run + `if (!cancelled) setState(...)` гард корректно
  фильтрует stale-ответы. AbortController дал бы только экономию
  сети — отдельная задача категории «оптимизация», не баг.
- [ ] **OTP attempt counter (S-4):** OTP /verify-code сейчас
  защищён только slowapi per-IP лимитом + Redis-key lookup. Глобальный
  per-telegram-id счётчик lockout-decision'а (через PrivateCore)
  закрыл бы коллективный multi-IP brute. Lower priority — структурно
  лук-ап-by-key уже почти constant-time.
- [ ] **JWT user revocation (jti):** user-tokens сейчас живут до
  expire (7 дней) без возможности отозвать. Admin-tokens уже
  поддерживают jti+Redis-blocklist — расширить на user-tokens.
- [x] **HLS path-traversal review:** проверены HLS-роуты
  (`hls.py:master/variant/segment`), `cover_proxy`
  (`tracks/discovery.py:cover_proxy`), `video_proxy`
  (`tracks/playback.py:video_proxy`), `secure_static.py` (token
  gate), StaticFiles mount, и весь upload-pipeline (`core/s3.py`).
  Все векторы защищены: `track_id: int` валидируется FastAPI;
  `variant` — allowlist `{"hi","lo"}`; `segment` — strict
  `endswith(".ts") + segment[:-3].isdigit()`; `cover_proxy.key` —
  `".." in key` + `startswith("/")` + allowlist-префиксы;
  upload-keys всегда uuid4-composed, user filename для video
  проходит `re.sub(r"[^\w.\-]", "_", ...)[:100]`. Path-traversal
  уязвимостей не найдено.
  - Побочное наблюдение (не path-traversal, но безопасность):
    `cover_proxy` обслуживает префиксы `voice/` и `chat_photos/`
    — приватный контент. Защита capability-by-key: ключи uuid4-hex,
    угадать нельзя, но логирование/утечка ключа = доступ. Стоит
    рассмотреть auth-check для этих двух префиксов отдельно (или
    вынести их в отдельный signed-URL endpoint). Не блокер.
- [ ] **`cover_proxy` private-content hardening:** найдено в HLS
  review — `voice/` и `chat_photos/` обслуживаются через
  публичный `cover_proxy` без auth. Защита только по
  capability-by-key (uuid4 hex). Рекомендуется: вынести в
  отдельный endpoint с авторизацией владельца/собеседника, или
  использовать signed URL.
- [ ] **WebSocket DoS-защита:** `ws.py` транслирует всем online без
  лимита по размеру очереди — отдельный аудит + bench.
- [ ] **Black-cleanup unrelated files:** при чтении проекта черновик
  заметил pre-existing non-black-compliant блоки в `app/api/v1/auth.py`,
  `app/services/track_response_build.py`. Можно прогнать `make format`
  отдельным cosmetic-коммитом.
- [ ] **Legal: вычитка `/legal/anti-abuse-signals` под 152-ФЗ:** в Mini
  App добавлены страница и ссылка из баннера согласия; текущий текст в
  `frontend/src/views/legalContent.ts` — инженерный черновик. Нужна
  юридическая правка, синхронизация с `docs/legal/PRIVACY_POLICY.md`
  (п. 7.5) и финальная публичная редакция.

## Upload UX optimization (2026-05-11)

- [x] **Upload-flow: автозаполнение + drafts + lyrics editor + post-upload SSE**
  — четыре независимых улучшения визарда загрузки трека:
  - **Phase A (auto-metadata)**: новый `frontend/src/lib/audioMetadata.ts`
    — нативный ID3v2.3/2.4 парсер (title/artist/album/year/genre + APIC
    cover) без npm-зависимостей, fallback на парсинг имени файла.
    `UploadFileTab` запускает извлечение асинхронно при выборе аудио,
    пред-заполняет пустые поля Details/Cover и показывает clearable
    «Auto-filled» чипы. Если у файла есть APIC — обложка пред-заполняется
    с пометкой «From audio file».
  - **Phase B (drafts/resume)**: новый `frontend/src/lib/uploadDraft.ts`
    — localStorage-схема (TTL 48h, key `dotsound:upload-draft:v1`).
    `UploadFileTab` сохраняет состояние с debounce 500мс; `UploadView`
    при mount показывает баннер «Continue / Discard» если черновик есть.
    Аудио и cover Blob не сохраняются — пользователь перепривязывает файл.
  - **Phase C (post-upload SSE)**: новый `app/api/v1/tracks/processing.py`
    — endpoint `GET /tracks/{id}/processing/{events,status}` с owner-check.
    Стадии opaque (`uploaded`, `cover`, `audio_analysis`, `lyrics`, `ready`,
    `error`) — без имён внутренних tier-ов / провайдеров. Снапшот
    собирается из `ComputeJob` (audio_features, catalog_normalize),
    `TrackLyrics` и `Track.cover_key`. Polling-based SSE (2с тик, 5 мин
    timeout). Frontend `UploadProgressView` подписывается через
    EventSource, fallback на `getProcessingStatus`. После Submit визард
    переключается на progress-view с CTA «Open track» / «Upload another».
  - **Phase D (lyrics editor)**: `LyricsEditor` получил импорт `.lrc`
    (новый `frontend/src/lib/lrc.ts` парсит `[mm:ss.xx]` + метаданные
    `ti/ar/al/offset`), live-подсветку строки при play (`stampedIndex`
    из `currentTime`), Space/Shift+Space hotkey на шаге sync, ±50мс nudge
    кнопки на активной строке, и кнопку «Auto-detect lyrics» (вызывает
    существующий `POST /tracks/{id}/lyrics/auto`) для пост-загрузочного
    режима с trackId. Paste с LRC-таймкодами в textarea авто-импортирует.
  - i18n: `i18n_extra2_{en,ru}.json` (`redesign.upload.file.autoFilled*`,
    `coverFromTag`, `draftBanner.*`, `progress.{stage,hint,cta}*`),
    `i18n_extra_{en,ru}.json` (`lyrics.editor.{importLrc,autoDetect,
    nudge*,lrcEmpty,lrcInvalid,autoDetectQueued,autoDetectError}`).
  - Стили: `redesign-upload.css` (`.ru-up-auto-chip*`, `.ru-up-label-row`,
    `.ru-up-auto-detecting`, `.ru-up-draft-banner*`, `.ru-up-progress*`)
    + `global.css` (`.le-secondary-actions`, `.le-secondary-btn`,
    `.le-info`, `.le-fs-nudge*`).
  - Boundary: opaque stage labels, no provider/tier leakage; ID3 parser
    runs client-side; new SSE polling avoids touching worker code paths.
  - Backend: `poetry run mypy app/api/v1/tracks/processing.py` green;
    `poetry run ruff check` green; `poetry run black --check` green.
  - Frontend: `npm run lint` (tsc --noEmit + legacy-toast guard) green.

## Admin panel hidden path + redirect (2026-05-09)

- [x] **Скрытый URL админ-панели и admin API через `ADMIN_PANEL_PATH`**
  — backend теперь принимает slug из `.env` (fallback `admin`) и
  применяет его к префиксам `/{slug}` и `/api/v1/{slug}`; frontend
  использует runtime-конфиг из `/api/v1/auth/config` только для admin
  и   убирает хардкод `/admin`. Для `"/admin/*"` добавлен редирект на
  главную, если фактический slug отличается. Обновлены `.env.example`,
  `README.md`, `docs/admin/onboarding.md`, `docs/admin/README.md`.
  Исправлена гонка: `AdminProvider` не запрашивает manifest до события
  `app-auth-ready`, чтобы не дергать `/api/v1/admin/...` до применения
  runtime-пути из `GET /auth/config`.

## Onboarding UX-рефакторинг (2026-05-09)

- [x] **Онбординг: 11-точечный UX-рефакторинг**
  — рефактор экранов Welcome/Genres/Swipe/Complete без изменений API и
  PrivateCore.
  - Логотип `.звук` / `.sound` в зависимости от языка интерфейса
    (`i18n_extra2_*.json` welcome.logo).
  - Прогресс-бар: убраны анимации `onbProgressFill` / `onbProgressPulse`,
    заполнение теперь статичное (нет «дёрганий»).
  - Поле имени: `enterKeyHint="done"` + `onKeyDown Enter → blur + submit`
    — клавиатура закрывается при нажатии «Ввод» на мобиле.
  - Жанры: аудио-превью при выборе жанра (15 с из очереди, случайный
    порядок, только один жанр одновременно). Отмена выделения → стоп.
    Аудио-реф локален внутри `GenresStep` (не конкурирует со свайпом).
  - Жанры: поиск-фильтр (`onb-v2-genre-search`) — ищет по подстроке
    названия жанра, те же превью при выборе в результатах.
  - Бэкдроп-карточка свайпа: убран `CardInfo`, добавлены
    `filter:blur(3px)` + `opacity: 0.35` через `.onb-v2-swipe-card--backdrop`
    — не видно текст следующего трека за текущей карточкой.
  - `touch-action: none` на `.onb-v2-swipe-card` — разрешён ручной
    горизонтальный свайп пальцем (framer-motion drag="x").
  - Обложка свайпа: иконка play/pause всегда видна (opacity 0.5 в покое,
    0.9 + анимация при `.is-playing`). Тап = toggle пауза/продолжение.
  - Авто-воспроизведение при смене карточки (`autoPlayedTrackRef` + effect
    на `[step, tasteIndex, tasteTracks]`).
  - Свайп: первые 5 треков обязательны; после них появляется кнопка
    «Завершить» + подсказка «продолжайте — чем больше оценок…».
    При исчерпании текущего пакета треков — тихая подгрузка следующего
    (radio-mode, `lastFetchCountRef` предотвращает двойные запросы).
  - «Перенести музыку»: исправлен редирект
    `/profile?import=1` → `/mini_app/profile?import=1`.
  - `tsc --noEmit` зелёный.

## Admin + global error UI (2026-05-09)

- [x] **Admin device-approval 429 / «что-то пошло не так»** — в логах
  `POST /api/v1/admin/auth/devices/request-approval` отдавал **429** (лимит
  `3/minute`); UI показывал сырое сообщение об ошибке. Лимит ослаблен до
  `20/minute`; в `DeviceApproval` дедуп автозапроса при двойном mount (Strict
  Mode), понятный текст при 429, кнопка повторной отправки кода;
  `AdminLogin` переводит 429 через i18n. Страницы ошибок приложения —
  `AppErrorFallback` + `.app-issue-panel`, тексты в `i18n_extra`. Заодно
  `warmTrackStreamCache` не дергает API с пустым/битым списком id (убирает
  лишние 422 в логах). `docs/design-system.md`, frontend `npm run lint` /
  `npm run build` green.

- [x] **Admin device-approval 400 без email** — тот же шаг после успешного
  `login` отдавал **400**: у аккаунта только Telegram, поля `email` нет,
  сервис раньше требовал почту для отправки кода. Теперь код уходит в
  Telegram через бота (`POST …/internal/send-auth-code`, те же
  `BOT_INTERNAL_URL` / секрет, что для прочих internal-вызовов). Во
  `frontend` нормализация `detail` ошибок API в строку (без «объект в React»).
  Подписи в `admin.device.*` обновлены под оба канала.

## Mini App: player progress wrong track (2026-05-08)

- [x] **Playback position applied to another track** — прогресс и
  метаданные трека писались в **два** ключа `localStorage`
  (`player-track` + `player-time`); при нескольких вкладках или
  чередовании записей возможна рассинхронизация (трек A + время B).
  Теперь один ключ `player-snapshot` (JSON `{ v, track, time }`),
  миграция со старых ключей, при сохранении убирается
  `resume_position_seconds` чтобы не тащить устаревший seek из кэша.
  `PlayerContext.tsx`; `npm run lint` / `npm run build` green.

## Mini App: TrackCard cover image (2026-05-08)

- [x] **Track list cover stuck as flat placeholder** — `re-tc-cover-wrap`
  used a fixed 56×56 box but `BeatPulse` was `inline-flex` without
  stretching, so `img` percentage sizing collapsed and only
  `--surface` showed. Wrap is now flex; pulse + `SharedCover` fill
  the tile. `SharedCover` adds a gradient frame and fades the image in
  on `onLoad`. `docs/design-system.md`. Frontend `npm run lint` /
  `npm run build` green.

## Mini App: LongPressMenu desktop hit-testing (2026-05-08)

- [x] **Track context menu (long-press / right-click) unclickable on
  desktop** — `LongPressMenu` overlay was `position: fixed` inside
  `SwipeRow`’s transformed drag layer, which breaks pointer hit-testing
  in Chromium-class browsers. Overlay is now portaled to
  `document.body`; backdrop uses `pointerdown` + `preventDefault` to
  dismiss and reduce click-through. `docs/design-system.md`. Frontend
  `npm run lint` / `npm run build` green.

## Mini App: compact track list cards (2026-05-08)

- [x] **Unified list `TrackCard` summary** — cover, title + inline
  artist, single `.track-card-summary` via `lib/trackCardFormat.ts`
  (duration · source · contextual time: last listen / liked / disliked).
  History and offline downloads use `TrackCard`; liked date merged into
  card; search pending-import rows and sheet “similar” aligned; mobile
  keeps summary visible. `docs/design-system.md`, i18n `trackCard.*`.
  Frontend `npm run lint` / `npm run build` green.

## Mini App: PlayerBar chrome (2026-05-08)

- [x] **Player bar: larger meta, prev + like always visible; desktop
  bar volume** — `PlayerBar.tsx`: volume popover only when
  `min-width: 561px`; mobile keeps prev/play/next/like/overflow; wide
  layouts insert volume before like. Coarse landscape: hide bar volume
  (`global.css`). `components.css` restores `pb-volume-*`. Docs
  updated. Frontend `npm run lint` / `npm run build` green.

## Mini App: Telegram swipe-to-dismiss (2026-05-08)

- [x] **Disable vertical Mini App dismiss on content swipe** — после
  `WebApp.ready()` / `expand()` вызывается `disableVerticalSwipes()`
  (`frontend/src/lib/telegram.ts`, Bot API 7.7+), чтобы свайп сверху
  вниз по контенту не сворачивал Mini App (на главной поведение уже
  маскировалось pull-to-refresh). Документация: `docs/design-system.md`.
  Frontend `npm run lint` / `npm run build` green.

## Lyrics: catalog + sync → compute worker (2026-05-08)

- [x] **Auto lyrics with sync:** если каталог отдаёт только plain text без
  таймкодов, текст сохраняется в БД и каскад снова вызывает
  `handle_tier_miss` → очередь `remote_whisper` для выравнивания по ASR
  (`app/services/lyrics_worker.py`).

## SoundCloud playback auto-skip (2026-05-08)

- [x] **Auto-skip unavailable SoundCloud streams in Mini App player** —
  `frontend/src/store/PlayerContext.tsx` now detects SoundCloud
  unavailability errors (deleted/private/unresolvable stream),
  shows an error toast, marks the track as unavailable for the current
  session, removes it from in-memory queue candidates, and immediately
  skips to the next track instead of stalling playback. `npm run lint`
  and `npm run build` are green (build refreshed `app/static/mini_app`).

## Playback resume fix (2026-05-08)

- [x] **Fix intermittent cross-track resume-position bleed in Mini App player** —
  in `frontend/src/store/PlayerContext.tsx` track switch now hard-resets previous
  audio element (`pause` + `src=''` + `load` + `currentTime=0`) before loading
  the next track, and periodic position persistence writes only when
  `lastTrackIdRef` matches the active `track.id`. This removes the race where
  old playback time could be saved under a newly selected track and improves
  state consistency during rapid switches. Frontend `npm run lint` is green.

## Home mobile genre-mixes spacing fix (2026-05-08)

- [x] **Fix oversized empty horizontal space in Home "Genre mixes" on phones** —
  added dedicated snap variant class for this carousel in
  `frontend/src/views/HomeView.tsx` and narrowed item width to content
  (`width: max-content`) in `frontend/src/styles/redesign-home.css`
  (`.rh-home-genre-snap .h-snap__item`). Desktop layout remains unchanged;
  frontend `npm run lint` is green.

## TrackCard access label in sheet (2026-05-08)

- [x] **Third-party stream access copy only in TrackCardSheet** —
  removed `trackCard.accessStream` from list `TrackCard.tsx`; sheet
  `tcs-source-info` shows `.tcs-access-mode-line` + existing source /
  disclaimer when applicable; `docs/design-system.md`. `npm run lint`
  green.

## TrackCard mobile density (2026-05-08)

- [x] **Compact list `TrackCard` on narrow viewports** — `max-width:
  560px`: smaller padding/covers, hide meta/source/non-private badges,
  extra `#main` bottom padding + `.track-list` spacing; `redesign-tracks.css`
  cover sizes; `docs/design-system.md`. `npm run lint` green.

## Artist carousels: mouse drag scroll (2026-05-08)

- [x] **Desktop drag on artist top-tracks + releases carousels** —
  `useHorizontalPointerDragScroll` (mouse only; `cursor: grab`), wired
  in both panels; `docs/design-system.md`. `npm run lint` green.

- [x] **Carousel snap + arrows: rAF scroll animation** — native
  `scrollTo/scrollBy(smooth)` unreliable in WebView; `horizontalScrollAnimate.ts`
  eases `scrollLeft` over `HORIZONTAL_PAGE_SCROLL_MS`; hook + arrow buttons.
  `npm run lint` green.


## Artist page: catalog releases carousel (2026-05-08)

- [x] **Releases section heading vs station card** — section uses
  `artist.catalog_releases_title`; `dotsound_sc_artist_station` rows
  sort first with title `catalogReleasesSimilar`; modal title matches
  section. `docs/design-system.md` updated.

- [x] **ArtistView catalog releases: below top tracks, 3-up carousel +
  sheet** — `ArtistCatalogReleasesPanel.tsx`, `.rf-artist-releases*`,
  RU/EN keys, `docs/design-system.md`. `npm run lint` / `npm run build`
  green.

## Artist page: popular tracks carousel + modal (2026-05-08)

- [x] **ArtistView popular tracks: 3-up snap carousel + «Ещё» sheet** —
  `frontend/src/components/ArtistView/ArtistTopTracksPanel.tsx` (swipe;
  `h-snap__arrow` on `≥768px` + fine pointer), full list in bottom sheet
  via `api.getAllArtistTracks` + `TrackList`; `api.getArtistTracks` gains
  optional `size`; `docs/design-system.md` + RU/EN i18n. `npm run lint`
  / `npm run build` green.

## PlayerBar mobile touch ergonomics (2026-05-08)

- [x] **Refine bottom player bar for phone use** — in
  `frontend/src/styles/global.css` hidden seek thumb for coarse pointers
  (mobile touch) to remove redundant dot on progress strip; in
  `frontend/src/styles/components.css` increased `.pb-ctl-v2` gap on narrow
  widths and **overflow menu** spacing: `.pb-overflow-menu` is a flex column
  with `gap` + roomier `.pb-menu-item` padding / `min-height: --tap-comfort`
  under `max-width: 560px` (queue, playlist, EQ, shuffle, etc.). Frontend
  `npm run lint` is green.

## Onboarding v2 — fresh wizard (2026-05-08)

- [x] **Onboarding v2** — переписан с нуля под единый flow
  Welcome → Profile → Genres → Swipe → Complete без шага «artists/moods»
  (вкус собирается через жанровые «пузыри» и Tinder-style свайп треков).
  - Backend (`app/api/v1/onboarding.py`, `app/services/onboarding_service.py`,
    `app/schemas/onboarding.py`):
    - `GET /onboarding/bootstrap` — single-shot: status + profile defaults
      + locale-curated `genre_bubbles[{genre, track_count, sample_cover_keys}]`
      + `show_import_offer` (через `should_offer_import_in_onboarding`).
    - `GET /onboarding/profile-defaults` — `derive_default_display_name`
      + `_DICEBEAR_IDENTICON` fallback для аватара + `suggested_initials`.
    - `POST /onboarding/profile` — сохранение `display_name` (валидация
      через PrivateCore `is_display_name_valid`), `locale`,
      `use_default_avatar`; `OnboardingProfileSubmitResponse` отдаёт
      финальный URL аватара и флаг `profile_completed`.
    - `GET /onboarding/taste-swipe?count=5` — отдаёт упорядоченные треки
      через PrivateCore `order_taste_swipe_tracks` (rotates genre/locale).
    - `POST /onboarding/taste-swipe` — батч из `like/dislike/skip` решений,
      создаёт записи в `LikeRepository` / `DislikeRepository` и помечает
      `calibration_completed=true`.
    - `OnboardingService.get_genre_bubbles` — выборка top-3 cover_keys
      на жанр через window-функцию `func.count().over()`.
    - `process_activation_event` уже возвращает merged meta с
      `ms_from_auth_server` (использовалось во фронте).
  - PrivateCore: `services/onboarding_policy.py` —
    `derive_default_display_name`, `is_display_name_valid`,
    `pick_default_genres_for_locale`, `should_offer_import_in_onboarding`,
    `trim_genre_bubbles`, `order_taste_swipe_tracks`,
    `has_minimum_taste_signal`, константы `GENRE_BUBBLE_COUNT`,
    `TASTE_SWIPE_TRACK_COUNT`, `TasteSwipeConfig`, `TasteTrackInput`.
  - Frontend (`frontend/src/components/Onboarding/OnboardingV2.tsx`):
    - 5 шагов в одном файле + sub-components `WelcomeStep` / `ProfileStep`
      / `GenresStep` / `SwipeStep` / `CompleteStep`. Полный motion
      (Framer Motion) c respect `prefers-reduced-motion`.
    - `AvatarBuilder` (загрузка через `api.uploadAvatar` 2 МБ ограничение,
      reset-to-default), `GenreBubble` (4-cell collage из cover_keys или
      placeholder, `is-selected` стиль).
    - Tinder-style `SwipeCard`: `useMotionValue` + `useTransform` для
      `rotate` и `LIKE`/`NOPE` бейджей (порог 110 px), aux-кнопки
      dislike / skip / like, hidden `<audio>` для preview по tap по карте.
    - Smart skip: `POST /onboarding/smart-skip` (PrivateCore решает, что
      применить); progress bar из 3 dots для основных шагов;
      `welcome` и `complete` без skip.
    - Hooks-events: `trackActivationEvent('onboarding_step_view')`,
      `'onboarding_step_complete'`, `'onboarding_complete'` /
      `'onboarding_skip'`.
    - Полная локализация под `redesign.onboardingV2.*` ключами в
      `frontend/src/locales/i18n_extra2_{ru,en}.json`.
    - `App.tsx` теперь монтирует `OnboardingV2` вместо старого
      `Onboarding`. Старый `Onboarding.tsx` + `OnboardingImportStep`
      + `OnboardingGenreScreen` остаются в репо как legacy и удаляются
      отдельным cleanup-коммитом (нет других потребителей).
    - `frontend/vite.config.ts` получил `redirectRootToMiniApp` middleware:
      запросы на `/` и `/mini_app` (без trailing slash) теперь 302
      редиректятся на `/mini_app/` в dev/preview серверах.
  - Тесты: 25 onboarding-тестов зелёные
    (`tests/app/services/test_onboarding_service.py`,
    `tests/app/api/v1/test_onboarding.py`); ruff/black по
    `app/api/v1/onboarding.py`, `app/schemas/onboarding.py`,
    `app/services/onboarding_service.py` clean. `tsc --noEmit`
    + `npm run build` зелёные (PWA precache 41 entries).
  - Follow-up: вычистить `Onboarding.tsx`/`OnboardingImportStep`/
    `OnboardingGenreScreen` из репо отдельным коммитом, как только
    станет ясно, что rollback не нужен.

## Mini App: глобальный mobile-first рефакторинг (2026-05-08)

- [x] **Mini App: глобальный mobile-first рефакторинг (адаптив + жесты + tap-targets)**
  — пройден аудит всей публичной части и выкачен один большой проход полировки
  под телефон без изменений API, PrivateCore и ComputeWorker.
  - Адаптивные токены `tokens.css`: `--tap-comfort/--tap-large`, ответвлённые
    `--layout-nav-h/--layout-player-h/--layout-content-gutter/--layout-section-gap`
    с media queries `(max-width: 360px)`, `(orientation: landscape) and
    (max-height: 500px)`, `(min-width: 768px)`. Legacy `--nav-h/--player-h`
    в `global.css` теперь биндятся к новым токенам.
  - `global.css` mobile-first слой: `.line-clamp-1/2/3`, `.touch-target`,
    `.no-scrollbar`, `.safe-bottom-pad`, `.sr-only`; tap-target нормализация
    `.ctrl-btn/.icon-btn/.nav-btn/.play-btn` под `pointer: coarse` (≥44px) +
    форм-контролы (`min-height: var(--tap)`, `font-size: 16px` чтобы убрать
    iOS-зум при focus); landscape-секция для `#player-bar/#pb-row` (компакт,
    `#pb-time/.pb-volume-wrap` скрыты), narrow-phone tweaks для view-header,
    `.track-card/.pb-cover/.pb-title/.pb-artist`; tablet (≥768px) шире gutter,
    desktop (≥1280px) центровка `.view` с `--content-max-width: 1200px`;
    `#main` overscroll-behavior contain; глобальный `:where()` focus-visible.
  - `redesign-shared.css`: glass-pill `.ptr-indicator` со state-машиной
    `idle | pulling | armed | refreshing`, `.sheet-inner--snap-medium/--snap-tall`,
    `.sheet-handle-zone { min-height: 28px }` для удобного захвата.
  - `redesign-nav.css`: narrow-phone padding, landscape (labels off,
    иконки в ряд), tablet centering.
  - `redesign-player.css`: narrow-phone now-playing, landscape split
    (`.rp-now__split` + `.rp-now__split-right`), wide desktop cap cover
    `min(48vw, 420px)`, компактные `--player-h` 72/56px на narrow/landscape,
    visual swipe-up `.rp-player-bar__hint`.
  - Sheet primitive (`components/ui/Sheet.tsx`): pointer-capture, rubberband
    easing, `snap='auto'|'medium'|'tall'`, чище cleanup transform/transition.
  - PullToRefresh: `hooks/usePullToRefresh` теперь возвращает `armed` и
    единожды стреляет `hapticSelection()` при пересечении threshold; общий
    `components/ui/PullToRefreshIndicator.tsx` (мигрирован `HomeView`,
    добавлен sr-only live region); ключи `redesign.home.ptrRelease` для
    RU/EN.
  - `PlayerBar` JSX: `<span class="rp-player-bar__hint">` swipe-up affordance
    над seek; seek thumb стабильно видим под `pointer: coarse`.
  - `NowPlayingView` JSX: добавлены wrapper-блоки `.rp-now__split` и
    `.rp-now__split-right` (в портрете `display: contents`, в landscape
    активируют 2-column grid).

## Smart-buffering / pre-fetch (2026-05-06)

- [x] **Smart predictive audio buffering (Mini App)** — единый
  PrefetchManager на фронте, IndexedDB warm-index + Service-Worker
  Cache API (через `vite-plugin-pwa` runtimeCaching) для HLS-сегментов
  и progressive-audio.
  - PrivateCore: `services/prefetch_policy.py` — константы и decision
    функции (`decide_lookahead`, `decide_max_storage_bytes`,
    `decide_warm_segments_per_track`, `should_prefetch_in_context`,
    `build_policy_snapshot`) + `NetworkProfile`/`PrefetchPolicySnapshot`
    + 24 unit-теста.
  - Backend: `GET /api/v1/prefetch/policy` (stateless) принимает
    client-hints (`effective_type`, `save_data`, `downlink`,
    `quota_bytes`) и отдаёт snapshot из PrivateCore. Pydantic-схема
    `app/schemas/prefetch.py`, тесты `tests/app/api/v1/test_prefetch.py`.
  - Frontend: `lib/prefetch/PrefetchManager.ts` (priority queue,
    semaphore, network listener, IndexedDB LRU), `store/PrefetchContext.tsx`
    + `usePrefetch`/`usePrefetchTracks`, тоггл «Умная буферизация» в
    `SettingsSheet`. Интеграция в `PlayerContext` (доп. слой к
    in-memory gapless handoff).
  - Триггеры prefetch: `HomeView`, `ArtistView`, `GenreMixView`,
    `WeeklyTopView`, `WeeklyMixView`, `DailyMixView`, `UserChoiceView`,
    `LikedView`, `SearchView` (top-3), `TrackCardSheet` (similar),
    `ChatBubble` (shared track), deep-link `/track/:id`,
    `continue_on_app_start` (последний трек history).
  - SW caching: HLS manifests SWR, HLS-segments CacheFirst (240
    entries, range-requests), progressive audio CacheFirst
    (`purgeOnQuotaError`).
  - Third-party stream треки (`access_mode == 'third_party_stream'`,
    SoundCloud/YouTube/Bandcamp) не кешируются локально — только
    metadata + URL warm-up через существующий `audio_cache_prefetch`.

## Mini App / .sound UI (2026-05-04)

- [x] **Mini App: warm-start без повторного бренд-сплэша (2026-05-08)** —
  устранено частое повторное появление глобального `.sound` loading-screen
  при самопроизвольных refresh в мобильном WebView. В `frontend/index.html`
  добавлен warm-boot cache в `sessionStorage` (`ds:last-ready-at`), логика
  мгновенного скрытия loader на «тёплом» старте и `pageshow`-обработка для
  bfcache. В `frontend/src/App.tsx` отключён React splash-screen на тёплом
  старте (init идёт в фоне без повторного бренд-экрана). Проверка:
  `npm run build` зелёный.

- [x] **Backend tech debt: targeted mypy + tests pass (2026-05-08)** -
  `AlbumService` fixed admin-actor resolution path (`_resolve_user` +
  strict `None` guard in `_assert_admin_actor`) to avoid runtime
  attribute access on missing user and make `allow_admin` path explicit;
  `cover_generator` draw context typing corrected (`ImageDraw.ImageDraw`);
  `media_service` switched to `Image.Resampling.LANCZOS` + explicit PIL
  image typing; `AlbumRepository._next_album_position` hardened for
  nullable scalar edge-case. Added service regression test for admin
  override authorization (`tests/app/services/test_album_service.py`).
- [x] **Backend tech debt: likes/dislikes typing cleanup (2026-05-08)** -
  tightened SQLAlchemy typing in `LikeRepository`/`DislikeRepository`:
  expression helpers now return `ColumnElement[bool]`, source-filter
  builder signatures are typed, and delete result handling uses safe
  `rowcount` extraction without `Result.rowcount` static-typing breakage.
  Also typed `TrackRepository` shared predicates to reduce downstream
  `no-untyped-call` debt.
- [x] **Backend tech debt: service typing fixes (2026-05-08)** -
  fixed strict-typing regressions in isolated services:
  `UploadService.upload_track` now has explicit optional
  `BackgroundTasks`; `encryption_service` uses positional
  `AESGCM.generate_key(256)` to match current cryptography stubs;
  `search_index_service` dropped unsupported `ignore` kwargs on
  Elasticsearch delete calls (errors remain safely logged in the same
  exception path). Plus typed null-filter in `metadata` genres endpoint.

- [x] **Mini App: redesign /profile UX — follow-ups (2026-05-08)** —
  поверх первого редизайна: (1) `ProfileTrackList` переписан с
  i18n-заголовком («Мои треки» + бейдж-счётчик в стиле
  `.profile-actions-group__title`) и empty state с CTA «Загрузить
  трек» (вызывает `navigate('/upload')`); (2) аватар в обычном
  режиме стал кликабельным `MotionPress` — на desktop при hover
  и focus-visible появляется тонкий pencil-overlay
  (`.profile-avatar-hover-hint`), клик открывает edit mode; на
  мобиле скрыт через `@media (hover: hover)`, остаётся явная
  кнопка «Изменить профиль»; (3) settings cog продублирован в
  back-header подвью (`profile-header-actions--sub`), чтобы из
  Импорта/Жалоб/Дизлайков можно было сразу попасть в настройки
  без возврата на главный профиль. Затронутые файлы:
  `views/ProfileView.tsx`, `components/Profile/ProfileHero.tsx`,
  `components/Profile/ProfileTrackList.tsx`, `styles/global.css`,
  `locales/ru.json`, `locales/en.json`. tsc/lint/tests/vite build —
  зелёные.

- [x] **Mini App: redesign /profile UX (2026-05-08)** —
  убрали табы Профиль/Импорт/Жалобы из шапки, шапка теперь
  компактная (`profile-page-header`): заголовок + правый кластер
  иконок (notifications/admin/debug/settings). Подвью import/
  complaints/dislikes используют единый back-header. ProfileHero:
  центрированный layout, аватар 96/112px, заметная кнопка
  «Изменить профиль» во всю ширину под именем; Save/Cancel — пара
  широких pill-кнопок. ProfileActions переведён в iOS/Telegram-style
  список со сгруппированными секциями («Моя библиотека»: Загрузить,
  Импортировать, Мои плейлисты, Понравившееся, Дизлайки, Жалобы;
  «Подборки»: Mix-шорткаты + Recap). Добавлен `.profile-content`
  max-width 720px на десктопе; hover/focus состояния для всех
  кликабельных элементов; min-height 44px у CTA и 56px у строк
  списка для удобного тапа на телефоне. Удалены устаревшие
  CSS-блоки для `.profile-tabs*`, оставлен только используемый
  `.profile-settings-btn`. Затронутые файлы: `views/ProfileView.tsx`,
  `components/Profile/ProfileHero.tsx`,
  `components/Profile/ProfileActions.tsx`, `styles/global.css`,
  `styles/redesign-library.css`, `locales/ru.json`,
  `locales/en.json`. tsc/lint/tests/vite build — зелёные.

- [x] **Mini App: визуальный polish Home + Search (2026-05-08)** —
  Home: hero/tiles/artist chips получили мягкий glass-border, depth и
  desktop hover micro-interactions (lift + cover zoom). Search: genre
  discover/playlist/history получили более выразительные состояния
  hover/focus, badge для количества треков и более читаемый active-tab.

- [x] **Mini App: visual polish Library + Profile header (2026-05-08)** —
  Library: `Daily mix` карточка и табы получили более выразительный
  depth/hover/focus. Profile: верхняя панель вкладок и подшапка
  `dislikes` стали контрастнее и визуально чище (glass-border, мягкие
  тени, hover/focus states).

- [x] **Mini App: visual polish Artist + Now Playing (2026-05-08)** —
  Artist: hero/related artists/footer buttons получили depth и более
  аккуратные hover/focus состояния. Now Playing: topbar и tabs стали
  визуально чище, обложка получила мягкий hero-lift эффект на desktop.

- [x] **Mini App: visual polish Upload + Recap (2026-05-08)** —
  Upload: dropzone/cover/url-preview получили depth и понятные
  hover/focus состояния. Recap: top chrome, hero элементы и CTA-кнопки
  стали контрастнее и визуально “собраннее”.

- [x] **Mini App: visual polish Legal + Achievements (2026-05-08)** —
  Legal: секции переведены в более читабельный card-layout со sticky
  header. Achievements: плитки и detail-sheet получили depth, cleaner
  states и более выразительные hover/focus.

- [x] **Mini App: visual polish Chats + Playlists grid (2026-05-08)** —
  Chats: header и saved/search actions получили более чистый glass-depth
  и hover/focus states. Playlists: карточки сетки и cover-обложки стали
  выразительнее за счёт lift/zoom/contrast polish.

- [x] **Mini App: visual polish Album/Playlist hero + Genre tabs (2026-05-08)** —
  Album/Playlist: hero-обложки получили более выраженный depth и
  desktop lift/zoom эффект. Genre: hero и табы стали контрастнее, с
  cleaner hover/focus состояниями.

- [x] **Mini App: visual polish Radio + Share Sheet (2026-05-08)** —
  Radio: hero и `next track` карточка получили более выразительный
  glass-depth и cleaner hover/focus. Share Sheet: recap-card и collage
  блок стали контрастнее и визуально “плотнее”.

- [x] **Mini App: Radio — tap on disc toggles play/pause (2026-05-08)** —
  в `/radio` клик/тап по большому диску переключает воспроизведение
  (короткий тап, без конфликта со swipe next/prev).

- [x] **Mini App: visual polish NotFound + External views (2026-05-08)** —
  NotFound: экран 404 переведён в более аккуратный card-layout с
  cleaner CTA состояниями. External Track/Album: hero и source actions
  получили depth и более выразительные hover/focus состояния.

- [x] **Mini App: visual polish ArtistStats + Queue sheet (2026-05-08)** —
  ArtistStats: KPI/graph cards получили более выраженный depth и cleaner
  hover/focus states. Queue sheet: header/rows/covers стали контрастнее
  и визуально аккуратнее за счёт subtle lift/zoom polish.

- [x] **Mini App: visual polish Import picker + Chat bubble actions (2026-05-08)** —
  Import source picker: rows/icons/badges получили более читаемый depth
  и hover/focus polish. Chat bubbles: action/reaction controls стали
  контрастнее и аккуратнее в интерактивных состояниях.

- [x] **Mini App: visual polish Search artist strip + Featured playlists (2026-05-08)** —
  Search artist strip: аватары и подписи получили cleaner depth и hover
  feedback. Featured playlists: карточки и cover-обложки получили
  более выраженный lift/zoom/contrast polish.

- [x] **Mini App: visual polish Playlists auto rows + Share chat list (2026-05-08)** —
  Playlists auto rows: строки и иконки получили более читаемый depth и
  hover/focus feedback. Share chat list: карточки выбора чата стали
  контрастнее и аккуратнее в интерактивных состояниях.

- [x] **Mini App: visual polish Inline create button + Share modal header (2026-05-08)** —
  Inline create button: улучшены depth, hover/focus и контраст border.
  Share modal: header/surface и header-actions получили cleaner glass
  вид и более аккуратные интерактивные состояния.

- [x] **Mini App: visual polish Photo preview composer + Queue empty state (2026-05-08)** —
  Photo preview composer: footer/input получили cleaner contrast и
  более читаемый focus-state. Queue: section titles и empty state
  получили более структурный card-like вид.

- [x] **Профиль: дизлайки в блоке действий + адаптив (2026-05-08)** — убран четвёртый таб
  сверху; «Дизлайки» в `ProfileActions` после «Понравившееся»; подшапка «К профилю» +
  заголовок; вкладка «Профиль» активна и для подэкрана дизлайков; сетка действий 3–4
  колонки от 640/960px; блок «Ваше прослушивание» в карточке (`ListenerStats` + CSS).
- [x] **Lyrics auto cascade: fallback после catalog miss при with_sync (2026-05-08)** —
  `catalog_only_lyrics_task` больше не завершает job как terminal `not_found` для
  sync-запросов: при `catalog_no_match` и отсутствии text/synced payload вызывает
  `handle_tier_miss` и переводит задачу в следующий tier (remote/speechkit). Для
  text-only режима поведение прежнее (terminal miss + `lyrics_catalog_miss_at`).
- [x] **Добавление треков в плейлист (2026-05-08)** — `PlaylistsView`: пустое поле — первая
  страница каталога (12 playable) и «Ещё из каталога»; текстовый запрос **от 2 символов**
  — поиск по каталогу с той же пагинацией; **1 символ** — только фильтр медиатеки;
  медиатека показывается чанками по 12 + «Ещё из медиатеки». Одно нажатие добавляет трек,
  острова успех/ошибка; `PlayerBar` → `AddToPlaylistSheet`; `api.getPlaylists(page,size)`.

- [x] **Обложки пользовательских плейлистов (2026-05-07)** — загрузка/смена
  собственной обложки (POST/DELETE `/api/v1/playlists/{id}/cover`), флаги
  `cover_auto_suppressed` + `collage_generated_at`, одноразовый коллаж из
  обложек треков при ≥4 видимых треках (PrivateCore `playlist_cover_policy`),
  Mini App (`PlaylistsView`) и `cover_proxy` для префикса `playlist-covers/`.

- [x] **Admin + lyrics pipeline: жанр и настроение по тексту** —
  эвристика в PrivateCore (`text_genre_mood_infer`), автоприсвоение
  после `LyricsRepository.create_or_update`, batch prompt/import в
  админ-чеке и `LYRICS_DERIVED_GENRE_MOOD_ENABLED` в `.env.example`.
- [x] **View Transitions + React** — `flushSync` в колбэке
  `startViewTransition` в `App.tsx` (иначе снимок «нового» кадра до коммита
  React — пустой/чёрный экран при смене вкладок/маршрутов).
- [x] **Глобальный UI redesign `.sound`** — обновлены splash/loading,
  иконки PWA, домашний экран, поиск, лайки, профиль, admin shell и
  Telegram bot copy/keyboards без изменения backend API, PrivateCore и
  ComputeWorker.
- [x] **iOS 2026 global redesign — Stage G (Admin) + Stage I (Upload/Import) + Phase 3 polish**
  — AdminRangeSwitch, DataTable sticky-glass + MotionPress sort, StatusPill icons;
  DashboardRoute/TasksRoute/SchedulesRoute/TracksRoute/UsersRoute/ArtistsRoute/ContainersRoute
  migrated to MotionPress + AdminRangeSwitch + showIsland toasts; UploadFileTab split into
  wizard steps (UploadStepAudio/Details/Cover/Preview + UploadComboBox); URL import tabs
  unified via UrlImportTab; ImportActivityBanner → headless DynamicIsland driver;
  toast.* → showIsland migration across HomeView/TrackCard/TrackCardSheet/TrackList/ArtistView;
  PlayerBar overflow-menu → MotionPress; QueueSheet/NowPlayingView/SearchView/LegalView/
  FullscreenLyrics bare buttons → MotionPress; dead .import-activity-banner CSS removed;
  i18n keys added for all hardcoded RU strings.
- [x] **Search + Artist route regressions (2026-05-07)** — `SearchView`: параллельная
  загрузка `getDiscover` + `getFeaturedPlaylists`, секция редакционных плейлистов,
  исправлен пустой hint при непустом discover, навигация на `/playlist/:id` из строк
  поиска, `tabHasResults` и пустой стейт вкладки «Плейлисты». `ArtistView` (route):
  каталог релизов + дискография + `ArtistCatalogReleasePanel`, Telegram back для
  подэкрана релиза; legacy `components/ArtistView/ArtistView.tsx` переименован в
  `ArtistProfileStandalone` (не использовался в маршрутах).
- [x] **Mini App responsive touch (2026-05-07)** — breakpoint ~560px: `MotionPress`
  icon 36px на desktop fine-pointer / 44px на touch; PlayerBar элементы управления и
  меню под `--tap`; на узкой ширине лайк и «назад» в overflow; главная —
  4 top quick-tile (`MIX_SHORTCUT_TILES` + `homeShortcuts.ts`), остальные миксы/радио
  в `ProfileActions`; hero колонкой на телефоне; `TrackCard` owner кнопки через
  `MotionPress`, дубль visibility скрыт на узком экране; чат — back/bubble coarse;
  **итоги года** — пункт профиля и `/recap` только в декабре (`recapSeason.ts`),
  иначе stub.
- [x] **Desktop: отдельные клики артист / трек (2026-05-07)** — при
  `(min-width: 561px) and (pointer: fine)`: строка исполнителя ведёт на карточку
  артиста через `resolveArtistByName`, клик по названию трека/обложке — как
  раньше (воспроизведение в списках, карточка в плеере / Now Playing).
  Компоненты: `TrackCard`, `PlayerBar`, `QueueSheet`/`QueueRow`, `NowPlayingView`,
  главная (`HomeTrackTile`, hero-artist), `ChatBubble`; хуки
  `useDesktopFinePointer`, `useNavigateToArtistByName`.
- [x] **Редактирование аватарки профиля (2026-05-07)** — в режиме редактирования
  `ProfileView`/`ProfileHero`: выбор JPEG/PNG/WebP до 2 МБ, превью через blob,
  загрузка `POST /api/v1/users/me/avatar` при «Сохранить» (API уже было);
  отмена сбрасывает черновик фото и имя до baseline; острова ошибок через
  `showIsland`; ключи в `i18n_extra2_ru/en.json`.
- [x] **Медиатека: история прослушиваний — дата и длительность** (2026-05-07) —
  `GET /users/me/listen-history` добавляет в `TrackResponse` поля
  `last_listen_at` и `last_listen_seconds` (учёт вариантов воспроизведения);
  `HistoryList` и `TrackCardSheet` показывают дату/время и «прослушано mm:ss`;
  i18n `redesign.library.*`, `trackSheet.lastListen*`.
- [x] **Плейлисты: добавление только воспроизводимых треков** (2026-05-07) —
  `playlist_track_eligibility` + проверка при `POST /playlists/.../tracks` и админ-добавлении;
  поиск/`me/library` с `playable`, UI выбора в `PlaylistsView`, админ-пикер по
  владельцу (`for_playlist_owner_id`, `playable_only`), i18n.
- [x] **Upload UX redesign + genre search** — UploadView/Upload tabs получили
  iOS-like polish, добавлено умное combobox с ES-backed fuzzy hints и
  create-new-genre flow, плюс haptic feedback и аккуратные микро-анимации.
- [x] **Upload: profile-owned artist flow** — `one account -> one artist`
  ownership (backend by user id), unique-name enforcement with migration
  auto-dedupe, auto-rename owned artist on `display_name` update, and
  UploadFileTab mode switch (`I am this artist` vs manual artist).
- [x] **Home recommendations: richer highlight endpoint** —
  PrivateCore `home_highlight_policy` (kinds: `weekly_top` /
  `your_top` / `forgotten_treasures` / `staff_pick` /
  `personalized`, weighted blend с freshness-decay,
  cold-start фильтр персональных kind'ов); backend
  `HomeHighlightService` собирает кандидатов из
  `recommendation_service.get_weekly_top_playlist`,
  `stats_service.get_user_top_tracks`,
  `recommendation_service.get_forgotten_treasures_playlist`,
  и recent uploads (`track_repo.list_active`); per-user Redis
  cache TTL 10 мин (`HOME_HIGHLIGHT_TTL_SECONDS`); endpoint
  `GET /api/v1/recommendations/home-highlight` возвращает
  `{kind, reason_code, track_id, title, artist, cover_key,
  access_mode, catalog_type}` или `null` для cold-start.
  Frontend: `api.getHomeHighlight`, `HomeView` использует
  highlight для hero-карточки (eyebrow через
  `redesign.home.highlight.{reason_code}`, fallback на
  существующий `featuredSource`); i18n RU/EN.

## Админка / альбомы (2026-05-04)

- [x] **Admin: редактирование альбомов в UI** - колонка `tracks.album_position` (миграция `0071`), порядок треков в публичном `GET /albums/{id}`, API `/api/v1/admin/albums` (список, детали, PATCH, обложка, add/remove/reorder треков), маршруты `/admin/albums` и `/admin/albums/:albumId` (capability `tracks.manage`).
- [x] **Admin: плейлисты** - API `/api/v1/admin/playlists`, UI `/admin/playlists` и `/admin/playlists/:playlistId` (метаданные, состав, порядок; уплотнение `playlist_tracks.position` после удаления).
- [x] **Admin: artist catalog editor UX (2026-05-05)** - `ArtistCatalogEditor` release metadata + cover upload, per-track title/artist/description/cover, paged «all tracks» list; API `POST /api/v1/admin/tracks/{id}/cover`, `POST .../catalog/releases/{id}/cover`.
- [x] **Playback health / auto-hide (2026-05-07)** — миграция `0083`, PrivateCore `playback_health_policy.py`, события `track_playback_failure_events`, колонки `tracks.playback_*`, авто-`playback_suppressed_until`, фильтр публичных выборок, запись при исчерпании fallback и ошибках upstream-прокси, админ-списки + вкладки в `TracksRoute`, API `playback-health/*`, снятие авто-hide; admin PATCH поддерживает `sc_url` / `source_url` / `canonical_source_url`.
- [x] **Admin playback health UI (2026-05-07)** — модалка «Источники» (редактирование/очистка URL), серверная **Проверить** (`POST .../verify`), **Сброс меток**, **Полное восст.**, **Снять auto-hide**; PATCH с `exclude_unset` и очистка URL в `admin_update_track`.
- [x] **Lyrics: catalog без ASR-бэкоффа без текста + метка miss + sweep (2026-05-07)** — колонка `tracks.lyrics_catalog_miss_at`, `catalog_only` не эскалирует на Whisper/SpeechKit при miss; текст без таймкодов сохраняется как plain-only; карточка/`TrackResponse.has_lyrics` по непустому plain text; импорт и глобальная очередь через `LyricsService.enqueue_background_lyrics`; часовая `lyrics_discovery_sweep_task` в `scheduled_jobs`; фильтр `GET /admin/tracks?lyrics_catalog_miss_only=1`; UI: скрытие кнопки «Текст» и вкладки Now Playing без текста.

## Подписки на артистов и статистика (2026-04-30)

- [x] **artist_follows** - миграция `0068`, модель, репозиторий, сервис, API: `POST/GET /artists/{id}/follow`, `GET /artists/{id}/follow/status`. Авто-подписка при онбординге (`save_preferences`). `follower_count` + `monthly_listeners` в `ArtistDetailResponse`.
- [x] **Рекомендации по подпискам** - `RecommendationService._build_user_prefs` объединяет `preferred_artist_ids` (онбординг) и `followed_artist_ids` (follows) через `dict.fromkeys` (порядок + дедупликация).
- [x] **Похожие артисты через SC-станции (2026-05-01)** - `ArtistCatalogRepository.get_similar_artist_ids_from_stations` извлекает artist_ids из треков «похожее»-станций любимых артистов; передаются в `UserPrefs.similar_artist_ids` (PrivateCore); scoring: 0.5x vs прямых фаворитов. `sync_artist_similar_station_task` + on-follow/onboarding триггер в `ArtistFollowService._enqueue_station_sync_if_stale` (порог `artist_station_stale_threshold_days=7`).
- [x] **Авто-очередь full catalog sync на follow/onboarding (2026-05-04)** - `ArtistFollowService` теперь ставит `sync_artist_catalog_task` для stale-артистов (порог `artist_catalog_full_sync_stale_threshold_days=30`) и дедуп enqueue через Redis lock (`artist_catalog_enqueue_lock_ttl_seconds`), чтобы не спамить Taskiq при массовых подписках.
- [x] **Активные слушатели в месяц** - `artist_monthly_stats` таблица, `ArtistStatsRepository.count_active_listeners` (live из `listen_events`), `GET /artists/{id}/stats/listeners` (текущий месяц + история).
- [x] **Снапшот за прошлый месяц** - Taskiq задача `snapshot_monthly_artist_stats_task` (запускается вручную или через внешний cron `0 2 1 * *`). `ArtistStatsService.snapshot_all_artists`.
- [x] **Cron-расписание снапшота** - миграция `0069` seed'ит запись в `scheduled_jobs` с cron `0 2 1 * *` (TaskiqScheduler / scheduler_service).
- [x] **Расширить `artist_monthly_stats`** - миграция `0070`, колонки `total_plays`, `total_likes`, `total_followers`; `ArtistStatsRepository` + `ArtistStatsService` + схема + frontend types. Chart в ArtistView показывает данные в tooltip.
- [x] **Frontend: карточка артиста** - `follower_count`, `monthly_listeners` и кнопка «Подписаться» уже реализованы в ArtistView (2026-04-30).
- [x] **Frontend: отдельная страница статистики** - `/artist/:id/stats` с полноценными recharts-графиками (total_plays, total_likes, total_followers по месяцам). Базовый bar-chart unique_listeners уже есть в ArtistView.
- [x] **Бот: плеер - источник «Подписки»** - источник `follows` добавлен в inline-плеер; `GET /users/me/followed-artists/tracks` (backend), `get_followed_artists_tracks` (bot client), кнопка «Мои подписки» в меню.

## Соответствие 152-ФЗ / ПДн (backlog, продукт + инженерия)

- Перед публичным запуском: **согласовать с юристом/DPO** фактическую обработку ПДн с требованиями 152-ФЗ (и смежное): основания, при необходимости уведомительный/регистрационный контур, субпроцессоры (email, observability, ASR-облака, бэкапы), трансгран, сроки хранения, запросы субъектов, реагирование на инциденты. Опора на `LEGAL.md`, `docs/legal/PRIVACY_POLICY.md` (сейчас draft).
- **Скорректировать функционал** по итогам: ретеншн/удаление, минимизация полей, kill-switch внешних API, согласованность логов и бэкапов с политикой. Не полагаться на внутренние id вместо `telegram_id` как на «анонимизацию», сохраняются операторские обязанности.
- См. также: `docs/project_context.md` (compliance), `AGENTS.md` (Legal readiness).

## Критичные / Инфраструктура

- Система бэкапов: PostgreSQL + Redis + configs (локально)
- Система логирования: JSON structlog + Docker log rotation (тонкая настройка: `REDACT_LOGS`, `REDACT_LOG_IDENTIFIERS`, `LOG_THIRD_PARTY_LEVEL`)
- Outbound Tor pool: по умолчанию выкл., `TOR_POOL_ENABLED=true` — opt-in;
  альтернатива: `OUTBOUND_STATIC_PROXY_URLS` (список URL httpx, RR) —
  вместе с Tor не включаются (`app/services/outbound_proxy.py`).
- Taskiq worker: graceful shutdown (`WORKER_SHUTDOWN`: cancel `import_queue_dispatcher` / `lyrics_global_orchestrator` background tasks, `close_es` в воркере) - 2026-04
- Docker Compose `worker` service: taskiq modules aligned with root `main.py` (imports, lyrics queue, snippets) - 2026-04
- SoundCloud `get_stream_info`: progressive manifest 404 - try HLS transcoding before 502; other upstream HTTP errors - 502 - 2026-04-29
- Audio-compute worker download: OTT with `proxy=1` so Backend proxies SoundCloud progressive streams (worker no longer GETs time-bound CDN URL directly; avoids 403) - 2026-04
- LyricsJob pull claim: admin profile `remote_whisper` now maps to the same queued rows as `gpu_full` (TIER_PROFILE_MAP); tier availability heartbeat counts both - 2026-04-29
- Mini App плеер: после сбоя Hls.js fallback `GET /audio` отдавал 302 на M3U8, Chrome в `<audio>` M3U8 не декодируется - добавлен `?force_progressive=true` (прокси MP3 с S3) и хелпер `trackProgressiveAudioUrl` в плеере / оффлайн-кэше / админ-превью - 2026-04-27
- Плеер: после ошибки `getStream` карточка вызывала только `togglePlay` по пустому audio - повторное нажатие Play перезапускает `playTrack`; начальный HLS без fallback - reject; dev/admin: override URL потока в карточке (sessionStorage) - 2026-04-29
- Lyrics cascade: preserve **root** worker failure in `cascade exhausted` message (not only last tier gate, e.g. `speechkit_disabled`); `lyrics_jobs.request_with_sync` / `request_bypass_cache` for fallback dispatch; log `audio_compute_worker_fail` - 2026-04
- [x] **Taskiq/cron: weekly batch stale station sweep (2026-05-02)** - `ArtistCatalogRepository.find_stale_station_artist_ids(threshold_days)`; `sync_stale_stations_batch_task` в `artist_catalog_sync_worker` (enqueue per-artist `sync_artist_similar_station_task`); миграция `0069` seed'ит `scheduled_jobs` с cron `0 3 * * 1` (Пн 03:00 UTC).
- **Полное копирование аудиофайлов (MinIO) на удаленный backup-VPS**
  - Подключение к отдельному серверу по SSH
  - `mc mirror` MinIO -> remote, инкрементально
  - Шифрование трафика, ключевая аутентификация
  - Настройка через `.env` (`BACKUP_REMOTE_HOST`)
  - UI в админ-панели: запуск/статус/расписание бэкапа
- Админ-панель (frontend): Раздел управления бэкапами
  - Просмотр списка бэкапов, размер, даты
  - Ручной запуск полного бэкапа
  - Настройка расписания
  - Статус последнего бэкапа (OK / FAIL)
  - Кнопка восстановления (с подтверждением)

## Админ-панель (выполнено)

- **Полноценная админ-панель** (Phase 1-5)
  - Backend `/api/v1/admin/*`: auth (TOTP onboarding с QR, login, device approval, step-up, refresh, logout), dashboard, tracks/users/complaints (без inline SQL), tasks (lyrics_jobs + compute_jobs + Taskiq queues + worker audit), logs (Loki proxy), metrics (Prometheus proxy), system (services health, containers, migrations, feature flags на app_settings), audit (admin_actions_log + CSV export), security (login attempts, locked users, lockout release), WebSocket для realtime
  - Многоуровневая защита: admin TOTP + device binding + pending_device email-flow + step-up для критичных действий + Telegram-алерты + короткие 15-мин сессии + rotating refresh + CSRF double-submit + строгий CSP + brute-force lockout
  - Observability: Prometheus + Grafana + Loki + Tempo + cAdvisor через `docker-compose.observability.yml`, `app/core/observability.py` (metrics/tracing/Sentry с PII-фильтром), расширенный `/health/deep` (db/redis/s3/taskiq/loki/prometheus)
  - Frontend `frontend/src/admin/` как chunked secure bundle: AdminApp, routes, layout, recharts графики, TanStack Query/Table, Zustand stores, semantic state-tokens только для StatusPill (см. design-system.md)
  - Документация: `docs/admin/{README,security,onboarding,testing,nginx-example.conf}`
- UX (2026-04): `AdminPromptProvider` (модалки вместо `alert`/`confirm`), i18n для строк админки, динамический заголовок раздела в topbar, выдвижное меню на «узком» вьюпорте (<720px), сортировка колонок в `DataTable` на Users/Tracks/Tasks/Artists/queues
- Post-ingest фон: enqueue compute + lyrics cascade при новом треке (upload / SC import / telegram import); массовый SC - paced lyrics без дубля; админ Tasks - таблица compute + источник lyrics job - 2026-04
- Перенести admin-security policy in PrivateCore (см. выше)
- WebAuthn/Passkey как опциональный второй фактор

## Безопасность

- Scoped JWT для internal-token (bot_player, 15 мин TTL)
- IP whitelist + rate limit на internal endpoints
- hmac.compare_digest для secret comparison
- Аудио sanitization через FFmpeg перекодирование (payload уничтожается)
- Аудит-лог входов через бота (расширить login_history)
- Rate limit тюнинг под production нагрузку
- **Глубокая валидация загрузок (Layer 1)**
  - `python-magic-bin` для проверки magic bytes (`file_validator.py`)
  - Интеграция в audio upload, cover upload, video upload
  - Запрет двойных расширений (`.exe`, `.bat`, `.cmd` и др.)
- **Sanitization изображений (Layer 2)**
  - Pillow re-encode для обложек и аватаров (через `media_service.process_image`)
- [~] **Сканирование загрузок: режим `lightweight` или `clamav`**
  - Конфиг `upload_malware_scan_mode: none | lightweight | clamav` в `config.py`
  - `scan_service.py` stub (ScanResult, scan_bytes)
  - Документировано в `.env.example` с рекомендациями по VPS
  - Реализация `lightweight` режима (YARA + эвристики, PrivateCore)
  - Реализация `clamav` режима (clamd TCP/socket, quarantine flow)
  - Разделить слои: сигнатуры/эвристики/пороги в PrivateCore, clamd/quarantine orchestration в Backend
- **CSP и изоляция (Layer 4)**
  - `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff` на все ответы
  - `Content-Security-Policy: default-src 'none'` на медиа-ответы

## Граница Backend / PrivateCore

- **Плейлист «Выбор пользователей» + счетчик `play_count` (2026-04-27):** PrivateCore `playcount_policy` (qualify, `rank_user_choice_tracks`); `GET /api/v1/recommendations/user-choice`, секция `user_choice` в `GET /api/v1/recommendations/home`; `PublicPlayCountService` + Redis 24h-дедуп; залогиненные - сигнал listen; гости - `POST /api/v1/tracks/{id}/play`
- **Рекомендации (2026-04 / RU-first для всех):** `recommendation_language_policy` - `RU_STRATIFICATION_ALWAYS`, `DEFAULT_CYRILLIC_STRATA_RATIO`, cold-start affinity; `_merge_language_affinity` / похожие / fallback home / user-choice - стратифицированные пулы; см. `docs/private-boundary-inventory.md`
- **Recsys - Track A / Phase 1 (2026-04):** гибрид `genre_samples` + очередь 15s превью, `GET .../preview-queue`, track-preview сегмент, админ-CRUD и capability `recsys.genre_samples.manage`
- **Recsys - Track B1 / Phase 5 Backend (2026-04):** миграция `0060` (таблицы features/similarity), internal API `/api/v1/internal/compute/*` (HMAC), `compute_results_router`, post-upload enqueue, CLI `python -m app.cli.compute_backfill`, `track_features_builder` + тесты
- **Recsys handoff (2026-04-27):** удален каталог `docs/recsys-parallel/`; ссылка в `project_context` убрана; тест `test_backfill_dry_run_uses_patched_session` чинит патч `AsyncSessionLocal` в `app.cli.compute_backfill`
- **Immediate: перенести auth/email policy в PrivateCore**
  - `account_linking_service`: `_LINK_TTL`, `_LINK_EMAIL_TYPE`, `_LINK_PREFIX`, `_LINK_TG_PREFIX`
  - `account_linking_service`: импортировать `is_disposable_email` из `dotsound_private_core.services.abuse`
  - `email_auth_service`: `_2FA_SESSION_TTL`, `_MAGIC_LINK_TYPE`, `_2FA_SESSION_TYPE`, `_ML_PREFIX`
  - `email_auth_service`: policy генерации fallback OTP (6-значный код) перенести в helper PrivateCore
  - `email_sender`: текст TTL fallback-кода строится от `FALLBACK_CODE_TTL`, без hardcoded `5 minutes`
- **Route-layer SQL debt (Backend refactor, не PrivateCore)**
  - Перенесен inline SQL из `api/v1/admin/tracks.py`, `api/v1/admin/users.py`, `api/v1/admin/complaints.py` в `AdminService`/`AdminRepository`
  - `api/v1/metadata.py:get_popular_genres` и `api/v1/users.py:get_login_history` доступны через `AdminRepository`/admin endpoints
- **Перенести admin-security policy в PrivateCore**
  - Создан `dotsound_private_core/services/admin_security_policy.py` с константами и decision-функциями
  - Удален временный stub `app/core/_admin_security_constants.py`
  - Все backend модули (admin_auth_service, admin_device_service, admin_alert_service, admin_manifest_service, ws.py, observability.py) переключены на импорт из PrivateCore
  - Добавлен endpoint-контракт `ADMIN_ALERT_ENDPOINT` в `dotsound_private_core/contracts/internal_api.py` + URL builder `admin_alert_url` в `internal_bridge.py`
  - Реализован `handle_admin_alert` в DotSoundBot (`bot/api/internal.py`) с allowlist `chat_id` и HTML-escape
  - Тесты: PrivateCore 88 admin-related, Bot 9 admin alert, Backend smoke + repo

## Продукты: пять спринтов (реализовано в Backend, 2026-04)

- S1 **Radio** - `GET /api/v1/tracks/{id}/radio` (каталог + YouTube mix/search + materialize), флаги `RADIO_*` в `config`, политика `dotsound_private_core.services.radio_policy`
- S2 **Co-listen** - `co_listen_rooms` + `POST/GET/PATCH /api/v1/colisten/rooms`, `WS /api/v1/colisten/ws/{room_id}` (Redis pub/sub), `dotsound_private_core.services.colisten_policy`
- S3 **Author stats** - `GET /api/v1/tracks/{id}/author-stats` (владелец), `listen_events` + `play_count` + лайки, `author_stats_policy` (округление)
- S4 **Плейлисты коллаб** - `playlist_collaborators`, `playlist_invite_tokens`, `POST /playlists/{id}/invites`, `POST /playlists/invites/accept`, правка `PlaylistService` для **editor** коллаб
- S5 **Сниппеты** - `track_snippets`, `POST /tracks/{id}/snippets`, `snippet_worker` (Taskiq + ffmpeg), `snippet_policy` + gating `catalog_type`
- **Follow-up:** Mini App / бот (кнопки radio, colisten, UI статистики, accept invite), e2e-тесты, Prometheus-метрики `radio_*` / runbook; юридический sign-off third-party + сниппетов (см. `LEGAL.md`). Миграция: `alembic upgrade 0056`.

## Плеер в боте

- Inline аудио-плеер (3 трека, editMessageMedia)
- Выбор источника: Мои / Лайки / Лента
- file_id кэш в Redis
- Предзагрузка следующей пачки
- Фильтрация треков без файлов (playable_only)
- Расширить источники: плейлисты, подписки, рекомендации
  - Для источника "Рекомендации": алгоритм ранжирования и скоринг в PrivateCore, Backend/бот - адаптеры выдачи
- Shuffle / Random режим

## Интернационализация (i18n)

- **Английская версия сайта (базовая)**
  - `react-i18next` + `i18next-browser-languagedetector`
  - JSON-каталоги `ru.json` / `en.json` (ключевые экраны: Auth, Home, Nav, Search, Liked, Upload, Profile, Playlists, Settings)
  - Telegram `language_code` custom detector
  - Переключатель языка в SettingsSheet
  - Поле `locale` в модели User + PATCH /users/me
  - Alembic миграция `0024`
- i18n: мигрировать оставшиеся ~35 .tsx файлы на `useTranslation`

## Эквалайзер

- 8-полосный Web Audio EQ (32 Hz -- 16 kHz)
- Preset-система
- Серверная синхронизация настроек (`GET/PUT /api/v1/users/me/eq`)
- **Улучшения эквалайзера (v2)**
  - Параметрический Q-factor (ширина полосы) на каждой полосе
  - Визуализация АЧХ в реальном времени (canvas/SVG)
  - Дополнительные пресеты: Bass Boost, Vocal, Classical, Electronic
- **Продвинутая обработка (v3)**
  - Compressor/Limiter (`DynamicsCompressorNode`)
  - Stereo Balance / Pan
  - Loudness normalization

## PWA / Фоновый плеер

- Установка на устройство: `isTelegram()` по `initData` / user; `InstallPrompt` (iOS Safari / прочий iOS, Chromium `beforeinstallprompt`, fallback без BIP); manifest `id`, один `link` manifest
- Media Session API (lock-screen контроли: play/pause/next/prev/seekto)
- Браузерная версия с email auth + Telegram code auth
- **PWA-слой поверх текущего SPA**
  - `manifest.json` через `vite-plugin-pwa` (name, icons SVG, standalone, theme_color)
  - Service Worker: `NetworkFirst` для API, `CacheFirst` для статики
  - Иконки: 192x192 и 512x512 SVG в `frontend/public/`
  - Meta-теги: theme-color, apple-touch-icon, apple-mobile-web-app-capable
- Picture-in-Picture для видео-треков
  - `video.requestPictureInPicture()` в `TrackCardSheet.tsx`
- **Offline-кэш треков (сохранение для оффлайн-прослушивания)**
  - **Сохранение**: кнопка "Скачать" на TrackCardSheet; аудио кешируется в Cache API (`caches.open('offline-tracks')`)
  - **Хранилище**: IndexedDB для метаданных (track JSON, обложка blob, статус); Cache API для аудиофайлов
  - **Управление**: экран "Скачанные" (список, занято места, кнопка удаления); лимит по объему (настраиваемый, ~500MB)
  - **Оффлайн-режим**: Service Worker перехватывает `/api/v1/tracks/{id}/audio` и `/hls/` - если есть в кеше, отдаем локально
  - **Плеер**: `playTrack()` проверяет Cache API перед сетевым запросом; оффлайн-треки играют без интернета
  - **Синхронизация**: при появлении сети - sync play counts (Background Sync API); обновление метаданных
  - **Ограничения**: HLS-треки кешировать как один файл через fallback endpoint `/audio`; DRM/лицензирование не применяется (UGC-платформа)
- **Грамотный единый плеер для разных платформ / источников**
  - Привести к единому UX `ugc`, `licensed`, `external_reference`
  - Разделить `access_mode`: `internal_stream`, `third_party_stream`, `official_embed`, `external_link`
  - Показать пользователю понятный режим доступа: наш стрим / внешний поток / открытый источник
  - Для каждого источника определить допустимые механики playback и ограничения по Terms
  - Гармонизировать `PlayerContext`, `TrackCard`, `TrackCardSheet`, deep links и search/import UX
  - Не смешивать в UI внешний reference и внутренний storage-backed трек как один и тот же тип воспроизведения

## Видео к трекам

- Загрузка видео (`POST /tracks/{id}/video`, mp4/webm, 15MB)
- Удаление видео (`DELETE /tracks/{id}/video`)
- Выдача видео (`GET /tracks/{id}/video`, proxy из S3)
- UI: Фоновое видео (muted, loop) в TrackCardSheet + FullscreenLyrics
- **Оптимизация/сжатие видео**
  - Taskiq task `transcode_video` (`video_transcoding.py`): FFmpeg H.264 + AAC
  - Max 720p, CRF 23, `-preset medium`, `-movflags +faststart`
  - Thumbnail генерация (FFmpeg `-ss 1 -frames:v 1`)
  - `video_processing_status` + `video_thumbnail_key` на Track (миграция `0023`)
  - Upload -> temp S3 -> queue -> async transcode -> update status
- Увеличить лимит загрузки до 50MB (из PrivateCore `MAX_VIDEO_BYTES`)
- Адаптивный HLS для видео (как для аудио)
- Ограничение длительности видео (Canvas-стиль или длина трека)
- Учет видео в storage quota пользователя

## Метаданные трека

- Изменение `is_public` после загрузки (PATCH)
- Загрузка/замена обложки
- Загрузка/удаление видео
- Текст песни (plain text) + синхронизированные тайм-коды
- **Редактирование title, artist, genre после загрузки**
  - `TrackUpdateRequest` расширен (Optional поля title/artist/genre/description)
  - `TrackRepository.update_track()` + `TrackService.update_track()`
  - PATCH endpoint обновлен: принимает любую комбинацию полей
- Поле `description` в модели Track (TEXT, nullable)
  - Alembic миграция `651109411149`
- **Автоопределение текста песен (lyrics auto-detection)**
  - Весь пайплайн в PrivateCore (черная коробка)
  - Backend: тонкий адаптер (S3 download, вызов PrivateCore, сохранение в БД)
  - Выбор режима: "Определить текст" (без таймкодов) / "Определить текст + таймкоды"
  - Без таймкодов: synced_lines хранятся в БД, переключение без пересчета
  - Редактирование автосгенерированного текста, source manual/auto
  - Поддержка внешних треков без аудио (только текст)
  - Миграция 0030: колонка source в track_lyrics
  - Taskiq-задача generate_lyrics_task
  - API: POST /lyrics/auto, GET /lyrics/auto/status
  - Frontend: кнопки автогенерации, toggle таймкодов, i18n
  - Re-define fix: админ-кнопки с `bypass_cache=true` + расширенные debug-логи в карточке (шестеренка)
  - Search fallback fix: при miss по `(artist,title)` делаем retry по `title-only` и сохраняем cache alias
  - Stability fix (2026-04-25): remote catalog-align теперь получает `audio_seconds` от compute-worker для корректной шкалы времени; добавлен защитный rescue от схлопнутой line-sync таймлинии (когда строки прилипают к одному позднему якорю), плюс retry на отправку `result/fail` из worker.
- **Auto-lyrics: вынос тяжелой обработки на внешний GPU-сервис (далекое будущее)**
  - Отдельный сервер/сервис с GPU для обработки аудио
  - Backend отправляет аудиофайл во внутренний API PrivateCore, а PrivateCore уже сам решает, обрабатывать локально или вызывать внешний GPU-сервис
  - Интеграция через существующий `lyrics_provider` в PrivateCore (внешние детали - внутри черного ящика)
- **Karaoke после catalog + remote ASR align (пока не делаем):** UI показывает режим «караоке» только при `word_times` на строках **и** `sync_quality === "word"` (`LyricsPanel.tsx`, `FullscreenLyrics.tsx`). Ветка `POST .../audio-compute/.../result` с `align_text_to_precomputed_asr_timed_words` сейчас пишет в БД **только** line-level строки + `sync_quality=line` - словесные таймкоды с воркера в сохраненный JSON не переносятся. На будущее: после align приклеить/распределить `word_times` к выровненным строкам каталога (из `asr_timed_words` или исходных `synced_lines` воркера) и при успехе выставлять `word`, чтобы караоке снова работал при эталонном тексте.
- Теги (`tags`, JSONB или отдельная таблица)
- BPM auto-detection (background task, `librosa` / `essentia`)
  - Извлечение фич/пороги confidence и decision rules в PrivateCore, Taskiq orchestration и запись результата - в Backend
- Waveform generation (pre-render формы волны для UI)

## Чат и комментарии [FROZEN — legal hold (149-ФЗ ОРИ)]

> Раздел заморожен: чаты/p2p-обмен сообщениями отключены до
> оформления юрлица и подачи в реестр ОРИ. Не реализуем новые
> пункты, см. `docs/REGULATORY_DISABLED.md`.

- Чат: DM, группы, WebSocket real-time
- Реакции, вложения, голосовые сообщения, цитирование
- WebSocket: Redis pub/sub, presence, typing indicators
- Комментарии к трекам: CRUD, голосование, пин, скрытие; Mini App - секция в `TrackCardSheet` для публичных треков; сервис - комментарии недоступны при `is_public=false`; ответы на комментарии (`parent_id`, дерево вложенности)
- [x] In-app уведомления: лайк комментария и ответ (`comment_like`, `comment_reply`), переход из панели уведомлений к комментарию (`focus_comment_id`, подсветка ветки) - 2026-04
- [~] Доработки чата (обсудить отдельно)

## Карточка артиста (multi-source)

- [x] **Каталог дискографии (SoundCloud) - phase 1:** миграция `0063` - `artist_catalog_releases`, `artist_catalog_release_tracks`, `artists.soundcloud_user_id`, `artists.soundcloud_permalink`; SQLAlchemy-модели; без HTTP/синка (след. этапы 2–3)
- [x] **Каталог дискографии - phase 2:** `SoundCloudService.list_user_albums` (пагинация `next_href`), `fetch_track_by_id`, `expand_playlist_stub_tracks`, `ensure_soundcloud_ids_for_artist` + `ArtistRepository.find_by_soundcloud_user_id`; без Taskiq / оркестратора каталога (phase 3)
- [x] **Каталог дискографии - phase 3:** `ArtistCatalogSyncService` (`sync_full_artist`, `sync_single_release`), `ArtistCatalogRepository`, Taskiq `artist_catalog_sync_worker` (`sync_artist_catalog_task`, `sync_artist_catalog_release_task`), `catalog_uploader_id`, `SoundCloudService.fetch_playlist_by_id` / `download_artwork_as_cover_key`; без публичных/admin HTTP-рутов (phase 4–6); перед синком - `try_autofill_soundcloud_user_id_for_artist` (permalink / профильные URL из `source_profiles`, иначе первый хит user search) - 2026-04-28; тот же autofill вызывается из `AdminArtistCatalogService` при постановке full/release sync в очередь (раньше enqueue отсекал `NULL` до воркера) - 2026-04-29
- [x] **Каталог дискографии - phase 4:** публичное чтение каталога `GET /api/v1/artists/{id}/catalog/releases`, `GET /api/v1/artists/{id}/catalog/releases/{release_id}` - `ArtistCatalogReadService`, расширение `ArtistCatalogRepository`, схемы `app/schemas/artist_catalog.py`, pytest `tests/app/api/v1/test_artist_catalog_releases.py`; admin каталог: `app/api/v1/admin/artist_catalog.py`, `tests/app/api/v1/admin/test_admin_artist_catalog.py`
- [x] **Каталог дискографии - phase 5 (mini app):** карточки релизов и экран релиза с ordered track list в `ArtistView`, API-клиент и типы; воспроизведение через `TrackList` / `TrackCard` - 2026-04-28
- [x] **Каталог дискографии - phase 7:** `catalog_sync_policy` (PrivateCore), лимиты в `ArtistCatalogSyncService`, cooldown постановки в очередь в `AdminArtistCatalogService` + 429 в admin API, `ArtistCatalogRepository.latest_synced_at_for_artist`, `SoundCloudService.list_user_albums` - `(albums, truncated)` - 2026-04-28
- Policy-exception для явного source attribution (`source_name` + `source_page_url`) зафиксирован в `docs/ai-boundary-policy.md` (Backend + PrivateCore)
- PrivateCore: расширен контракт `ArtistInfo` полями `source_profiles`, `primary_source_id`, `discography`
- Backend: добавлены `artists.source_profiles` (JSON) и `artists.primary_source_id` (миграция `0039`)
- Backend API: `ArtistDetailResponse` и `/api/v1/artists/{id}` возвращают `source_profiles` и `primary_source_id`
- Frontend ArtistView: горизонтальный переключатель источников под аватаром + рендер bio/meta/discography по выбранному источнику
- Frontend ArtistView: полноэкранный просмотр аватарки с закрытием по overlay / кнопке / `Esc`
- Frontend ArtistView: отдельная строка `Источник: <source_name>` с кликабельной ссылкой на страницу источника
- Регрессионные тесты обновлены:
  - PrivateCore `test_artist_info_provider.py`
  - Backend `test_artist_enrichment_service.py`, `test_artist_enrich.py`, `test_artist.py`

## Предзагрузка треков

- Предзагрузка следующей пачки в боте (DotSoundBot)
- `GET /tracks/{id}/adjacent` (sequential/shuffle/repeat_one)
- hls.js с ABR (`startLevel: -1`, `enableWorker: true`)
- **Prefetch в Mini App / браузере (метаданные)**
  - `GET /tracks/{id}/queue?count=3` -- новый endpoint
  - `TrackRepository.get_next_tracks()` возвращает N следующих треков
  - Кеш в `PlayerContext` через `useRef` (`prefetchCacheRef`)
  - `playNext` использует кеш, fallback на `getAdjacentTracks`
- **Предзагрузка аудио следующего трека (gapless)**
  - При проигрывании текущего трека - начинается буферизация аудио следующего трека в фоне
  - Скрытый `<audio>` элемент (`preloadAudioRef`) с `preload="auto"` загружает URL следующего трека
  - Для HLS: создать второй `Hls` instance, привязать к preload-элементу, дождаться `MANIFEST_PARSED`
  - При `playNext` - swap: preload-элемент становится основным, мгновенный старт без буферизации
  - Запуск предзагрузки по порогу (например, текущий трек проигран на 75% или осталось < 30 сек)
  - Отмена предзагрузки при ручном переключении на другой трек
  - Ограничение: предзагружать только 1 следующий трек (экономия трафика)

## Идентификация загрузчика

- `uploaded_by_id` на Track (FK -> User с telegram_id)
- `created_at` / `updated_at` timestamps
- `RequestLoggingMiddleware` логирует `client_ip` в structlog
- **Расширенные метаданные загрузки (admin-only)**
  - Модель `TrackUploadMeta` (миграция `0022`): `upload_ip`, `upload_user_agent`, `upload_telegram_data` (JSON)
  - Заполнение при upload из `request.client.host` + headers
  - Admin endpoint `GET /admin/tracks/{id}/upload-meta`
  - PrivateCore: `UPLOAD_META_RETENTION_DAYS = 90`
- Taskiq job для автоудаления meta старше retention (GDPR)

## Удаление аккаунта

- **Soft delete с grace period (30 дней)**
  - `DELETE /api/v1/users/me` (body: `{"confirmation": "DELETE"}`)
  - `POST /api/v1/users/me/restore` -- восстановление в grace period
  - `deleted_at` на User (миграция `0021`)
  - PrivateCore: `account_deletion_policy.py` (GRACE_PERIOD_DAYS, is_within_grace_period, is_valid_confirmation)
  - Auth flow: soft-deleted пользователи в grace period проходят auth
- [x] Taskiq job для hard delete после 30 дней — `app/services/account_deletion_service.py` + `account_deletion_worker.py`, миграция `0078_user_hard_delete_anonymize_fks` (`messages.sender_id`, `track_comments.user_id` CASCADE → SET NULL), seed `daily-user-hard-delete` cron `30 3 * * *`; PrivateCore policy: `hard_delete_cutoff`, `build_anonymized_username`, `ANONYMIZED_DISPLAY_NAME`, `HARD_DELETE_BATCH_LIMIT`; комментарии и сообщения рендерятся как `Deleted user`; tests: PrivateCore +6, Backend +6 (2026-05-06).
- **Политика удаления данных**
  - Профиль, аватар, настройки EQ -- удалить
  - Лайки, дизлайки, подписки -- удалить
  - Сообщения в чатах -- анонимизировать ("Deleted User")
  - Комментарии -- анонимизировать
  - Плейлисты -- удалить
  - Треки -- выбор пользователя: удалить или оставить анонимно
  - S3 объекты -- удалить при удалении трека
- **Подтверждение удаления**
  - Повторная авторизация
  - Текстовое подтверждение ("DELETE")
  - Email/Telegram уведомление
  - Политики re-auth/cooldown/max-attempts для удаления страниц в PrivateCore

## Frontend / Mini App

- [x] Плеер / карточка трека / оверлеи: motion-токены, decay спектра при паузе, enter/exit (в т.ч. FullscreenLyrics), микро-виз в `PlayerBar` - 2026-04-29
- [x] Страница 404: контраст CTA, карточка, safe-area / адаптив - 2026-04-29
- **Покрытие Backend API клиентом:** инвентарь и приоритеты - `docs/api-frontend-coverage.md`; расширен `frontend/src/lib/api.ts`, исправлен `POST /users/me/avatar`, UI (OAuth disconnect, удаление аккаунта, похожие артисты), `adminApi.metricInstant`; регрессия - `scripts/check_openapi_frontend_coverage.py`
- Главная: CTA «Слушать/Play» - старт с первого трека плейлиста дня (дальше - существующий radio-prefetch в `PlayerContext`); карточка «плейлист недели» и экран `/weekly-mix` (API `weekly-playlist`).
- Восстановление позиции воспроизведения при перезапуске
- Монохром-фильтр в настройках
- Админ-панель: управление пользователями
  - Если добавятся баны/risk flags/anti-abuse actions, decision rules и пороги должны идти из PrivateCore
- Админ-панель: модерация контента
  - Пороги auto-hide/escalation и moderation policy держать в PrivateCore, панель - UI + вызовы Backend API
- Админ-панель: управление бэкапами (см. выше)

## Frontend оптимизация

- **Mini App (браузер): GPU / композитор** - смягчены токены стекла, фикс-панели `#nav` / `#player-bar` на `--glass-backdrop-fixed*`, липкий поиск на более легком blur; класс `ds-low-glass` при `prefers-reduced-motion` / `prefers-reduced-data`; без бесконечных splash/home; при play - легкий `pbPlayGlow` (откл. при reduce motion), статичный EQ в очереди; спектр на canvas ~12 fps, cap DPR, меньше столбцов - 2026-04
- **Waveform (карточка трека): снижение нагрузки на iGPU** - `setInterval` ~12 fps вместо RAF на частоте дисплея; буфер FFT без аллокаций каждый кадр
- **PlayerContext: CPU** - throttling обновлений `currentTime` в React (~10/s), flush при play/pause/seek/skip; виджеты и экраны без таймера переведены с `usePlayer()` на `usePlayerActions` / `usePlayerMeta`, чтобы не перерисовываться на каждый тик
- **SearchView: прогрессивная выдача** - `getTracks` / `searchSuggest` не ждут YouTube, Bandcamp, SoundCloud; внешние секции обновляются по мере ответа и могут отображаться до готовности блока «На платформе»
- **PlayerContext split (производительность)**
  - 3 контекста: `PlayerStateCtx` (currentTime, duration, isPlaying), `PlayerActionsCtx` (стабильные callbacks через useCallback), `PlayerMetaCtx` (track, volume, EQ, модалки)
  - 3 хука: `usePlayerState()`, `usePlayerActions()`, `usePlayerMeta()`
  - `usePlayer()` -- compat shim для плавной миграции
- **LikesContext оптимизация**
  - `useMemo` на value, `useCallback` на все функции
- **React Router (deep links, PWA)**
  - `react-router-dom` v7 (React Router)
  - Маршруты: `/`, `/search`, `/upload`, `/liked`, `/playlists`, `/chats`, `/chats/:id`, `/profile`, `/track/:trackId`
  - `BottomNav` через `useNavigate` + `useLocation`
  - `BrowserRouter basename="/mini_app"`
  - Browser back/forward, shareable URLs, deep links
- **Code splitting (lazy loading)**
  - `React.lazy()` для ChatView, UploadView, SearchView, LikedView, PlaylistsView, ChatsView, ProfileView
  - `hls.js` в отдельный chunk (`manualChunks`)
  - `<Suspense>` обертка для route-level lazy loading
- **TanStack Query (API кеширование)**
  - Автоматический кеш, дедупликация, stale-while-revalidate
  - Постепенное внедрение (endpoint за endpoint)
- Типизация: убрать 5x `Promise<any>` в `api.ts`
  - `ImportJobResponse` + `ImportAudioInfo` в `types/api.ts`
  - `genre` + `description` добавлены в `Track` interface
- CSS: рассмотреть разделение `global.css` (~2700 строк)

## Backend API

- YouTube import/playback: fallback на auto-выбор формата в `yt-dlp` при `Requested format is not available` (без 422/503 из-за жесткого format-string)
- YouTube import/playback: fallback по client-профилям `yt-dlp` при anti-bot (`Sign in to confirm you’re not a bot`) + возврат 503 вместо 422 для временной блокировки
- **Elasticsearch (поиск + suggest)**: индексы треков/артистов, Taskiq reindex/backfill, `GET /api/v1/search/suggest`, поиск треков с `q` через ES + PG fallback, bool/should (strict + fuzzy) для треков/артистов и саджеста, counter `elasticsearch_query_total` (op/outcome) в `observability`
- `artist_link_backfill_task` / `track_artists`: дедуп по `canonical` (PrivateCore + `resolve_and_link`), `ON CONFLICT DO NOTHING` в `link_track`, `begin_nested` + `error`/`error_type` в backfill
- `LOG_THIRD_PARTY_LEVEL` / `apply_third_party_log_levels` - уровень `urllib3`/httpx/ES/SQL-эха отдельно от `LOG_LEVEL`; Taskiq воркеры тоже при старте
- playable_only фильтр в track listing endpoints
- internal-token endpoint с полной защитой
- WebSocket: событие player.state для синхронизации
- Пагинация liked tracks (backend + frontend)
  - Backend: `page`/`has_more` в `UserLikesResponse`
  - Frontend: `LikedView` с "Показать еще" кнопкой

## Юридический аудит: анализ конкурентов (UGC + ст. 1253.1)

> **Цель**: изучить каждый сервис из списка на 2 вещи:
>
> 1. Наличие web-плеера / API для стриминга - возможна ли ретрансляция аудио на DotSound (аналогично SoundCloud: звук передается пользователю, плеер наш, мы оболочка).
> 2. Политика, соглашения, правовая реализация - что можно адаптировать для DotSound (тексты оферт, дисклеймеры, процедуры takedown, формы загрузки с подтверждением прав).

### Категория 1: Прямые аналоги (UGC + информационный посредник)

- **Musify.club**
  - Web-плеер: есть ли публичный стрим/API, можно ли встроить
  - Юридика: пользовательское соглашение (ст. 1253.1), страница `/contacts/legal` (перечень лицензий с ООО «АдвМьюзик» и др.), процедура DMCA/takedown, форма загрузки
  - Выводы: что адаптировать для DotSound
- **4beat.ru**
  - Web-плеер: стрим, embed, API
  - Юридика: пользовательское соглашение, форма загрузки трека (какие галочки/подтверждения прав требуют), страница правообладателям
  - Выводы: что адаптировать для DotSound
- **QPlet.ru**
  - Web-плеер: стрим, публичный доступ к аудио
  - Юридика: условия загрузки, онбординг артиста, оферта
  - Выводы: что адаптировать для DotSound
- **Созвук (sozvuk.ru)**
  - Web-плеер: стрим, embed, API для треков
  - Юридика: публичная оферта (ст. 1253.1), как оформлены права при загрузке, политика удаления по жалобе
  - Выводы: что адаптировать для DotSound

### Категория 2: Крупные платформы с UGC-компонентом

- **VK Музыка (vk.com/music)**
  - Web-плеер: закрытый API, возможности ретрансляции
  - Юридика: лицензионное соглашение (`vk.com/terms/music`), Content ID, как разделяют лицензированный и UGC-контент, процедура жалоб
  - Выводы: что адаптировать для DotSound
- **Яндекс.Музыка**
  - Web-плеер: закрытый стрим, ранжирование UGC vs лицензированное
  - Юридика: условия загрузки пользовательской музыки, как UGC показывается ниже официального в поиске
  - Выводы: что адаптировать для DotSound
- **ZVUK (zvuk.com)**
  - Web-плеер: стрим, партнерская модель
  - Юридика: условия для артистов, договоры с дистрибьюторами, требования к правам
  - Выводы: что адаптировать для DotSound

### Категория 3: Серая зона

- **Зайцев.НЕТ (zaycev.net)**
  - Web-плеер: стрим, API, легальная модель (100% лицензии с 2019)
  - Юридика: путь от UGC к лицензиям - что заставило перейти, пользовательское соглашение (написано юристами), страница правообладателям, процедура 5-дневного takedown
  - Выводы: какие тексты/процедуры адаптировать для DotSound
- **TRULA-music (trula-music.ru)**
  - Web-плеер: плеер + виджеты для стримеров
  - Юридика: оферта (ст. 1253.1), узкая ниша - как оформляются права
  - Выводы: что адаптировать для DotSound
- **Muzofond.fm / LightAudio.ru / HitMo (антипримеры)**
  - Web-плеер: открытый стрим, скачивание mp3
  - Юридика: нет явных лицензий, ссылаются на «пользователи загрузили», периодические блокировки Роскомнадзора
  - Выводы: какие ошибки НЕ повторять

### Итоговый отчет (после анализа всех сервисов)

- Сводная таблица: сервис / web-API / возможности ретрансляции / юридическая модель / риски / что адаптировать
- Список конкретных текстов для адаптации: оферта, дисклеймер, страница правообладателям, форма загрузки с подтверждением прав
- Рекомендации по изменению архитектуры DotSound на основе анализа

## Юридическая готовность

- Базовый legal package в репозитории
  - `LEGAL.md`
  - `docs/legal/archive/LEGAL_AUDIT_RU.md`
  - `docs/legal/USER_AGREEMENT.md`
  - `docs/legal/PRIVACY_POLICY.md`
  - `docs/legal/COPYRIGHT_POLICY.md`
  - `docs/legal/UPLOAD_RULES.md`
  - `docs/legal/LEGAL_TEXTS.md`
- Синхронизировать complaint/rightsholder flow во frontend и backend
  - `reason_type`, `rightsholder_name`, `proof_url` теперь проходят через schema -> route -> service -> repository -> UI
- Обязательный акцепт условий при `UGC` upload
  - Checkbox в `UploadFileTab.tsx`
  - backend validation в `api/v1/tracks/user.py`
  - логирование версии условий в `track_upload_meta`
- Постоянные guardrails для агентов и docs
  - `AGENTS.md`
  - `docs/ai-boundary-policy.md`
  - `.cursor/rules/legal-readiness.mdc`
  - `.claude/hooks` + `.claude/settings.json`: блок опасных shell-patterns, блок секретов, SessionStart контекст
  - `.cursor/rules/shell-safety.mdc` + `.cursor/rules/session-start-context.mdc` для эквивалентных guardrails в Cursor
- Явно размечен current MVP external playback
  - В `Track` добавлены `access_mode`, `source_platform`, `canonical_source_url`
  - `SoundCloud` import помечает трек как `third_party_stream`
  - UI показывает внешний источник и режим доступа
- На уровне модели разделены категории треков
  - В `Track` добавлен `catalog_type`
  - Базовое разделение: `ugc`, `licensed`, `external_reference`
  - `SoundCloud` -> `external_reference`, `upload/telegram` -> `ugc`
- Опубликовать legal docs в самом продукте как отдельные доступные страницы
  - `/legal` стал hub-страницей
  - Добавлены маршруты `/legal/terms`, `/legal/privacy`, `/legal/copyright`, `/legal/upload-rules`
  - Upload и complaint flow теперь ссылаются на конкретные legal docs
- Разделить на уровне модели/API `UGC`, `licensed` и `external-source` треки, не полагаясь только на текстовые дисклеймеры
- Проверить current MVP с собственным playback поверх stream URL стороннего сервиса для текущего внешнего источника (`SoundCloud`) и зафиксировать residual risk
- Разделить обычные пользовательские жалобы и надлежащее уведомление правообладателя в отдельные UX и workflow
- Базово разделить обычные жалобы и уведомление правообладателя в UX
  - `ComplaintModal` поддерживает режимы `user` и `rightsholder`
  - Правообладательский режим требует доп. поля и отдельный текст
- Internal checklist для Terms внешних источников
  - `docs/legal/SOURCE_TERMS_CHECKLIST.md`
  - rule/docs привязаны к проверке external-source integrations
- Сделать тексты внешнего импорта и поиска более честными
  - `SearchView` явно помечает SoundCloud как внешний источник
  - Текст предупреждает, что после добавления трек идет как внешний поток стороннего сервиса

## DevOps / CI

- **Branch coverage 95% (4 репо):** `scripts/check_branch_coverage.py` + `pytest --cov-branch` / `coverage.json` - порог `percent_branches_covered` (см. Makefile / `AGENTS.md`). Выполнено: полный прогон и проверка gate в Backend/PrivateCore/Bot/ComputeWorker.
- GitHub Actions: lint + test на PR (Backend, Bot, PrivateCore)
- Автоматический деплой на VPS
- Расширенный healthcheck (`/api/v1/health/deep` - БД, Redis, S3)
- Health monitoring + alerting (uptime check, внешний)

## Sprint 0..9 редизайна (2026-04, single-pass)

- Bot: like/dislike - добавлен Bearer + правильный internal id
- Frontend: `--progress` пробрасывается в `#pb-seek` (WebKit fix)
- Frontend: SW unregister только в dev-режиме
- Frontend: `env(safe-area-inset-bottom)` в `#nav`, `#player-bar`, `#main`
- PrivateCore: `is_within_grace_period` отсекает будущие `deleted_at`
- PrivateCore: `is_disposable_email` валидирует формат email
- PrivateCore: тесты для `account_deletion_policy` (15 кейсов)
- Backend: inline SQL вынесен из `artists.py`, `admin/audio_compute.py`
- Backend: `dependencies.require_capability` использует репозиторий
- Backend: `transcoding._upload_hls` использует `asyncio.to_thread`
- Backend: `TrustedHostMiddleware` через `settings.allowed_hosts`
- Bot: throttling middleware подключен к callback и inline_query
- Bot: внутренний HTTP-сервер binds `127.0.0.1` (через config)
- Bot: HTML escape во всех форматерах (`base`, `audio`, `inline`, `stats`)
- Bot: единый `mini_app_url` (убран `backend_base_url` для WebApp)
- Bot: internal API возвращает opaque error codes
- Bot: глобальный `errors` handler с user-friendly fallback
- Bot: prefetched URLs используются в `_edit_audio_batch` (gap-less)
- Bot: Dockerfile multi-stage с PrivateCore из родительской директории
- Frontend: дизайн-токены в `tokens.css` (8pt grid, motion, type scale)
- Frontend: `components.css` с Press, Sheet, Skeleton, EmptyState стилями
- Frontend: `Press`, `Sheet`, `EmptyState`, `SkeletonList`, `OfflineBanner`
- Frontend: расширен Icon-set (more-horizontal, queue, chevron-up/down)
- Frontend: Unicode заменен на `<Icon>` в FullscreenLyrics, PlaylistsView, ComplaintModal, TrackCard, PlayerBar
- Frontend: `installTelegramThemeBridge`, `installViewportListener`, `setBackButton`, `haptic`, `hapticNotification`
- Frontend: PlayerBar v2 - overflow menu + breakpoints + skeleton hit-area
- Frontend: TrackCard переключен на `usePlayerMeta` + `usePlayerActions`
- Frontend: CoverImage с `loading="lazy"` + `width/height`
- Frontend: aria-label/aria-pressed/aria-current на ключевых контролах
- Frontend: `useConfirm` переписан с правильным unmount cleanup
- Frontend: index.html splash сокращен с 1800ms до 1200ms safety cap
- PrivateCore: README актуализирован, версия `0.2.0`, policy с bounded-transport exception
- Backend: `/api/v1/health/deep` (DB / Redis / S3 ping)
- Backend: `X-Request-ID` отдается в заголовке ответа
- Docs: `docs/design-system.md`, `docs/redesign-rationale.md`

---

*Последнее обновление: 2026-05-16 (Admin playback filters and radio skip counters).*

## Session Updates (2026-05-06)

- [x] Admin dashboard UI refresh: interactive online history chart with range switch (15m/1h/6h/24h), trend badge, and additional RPS/latency cards in `frontend/src/admin/routes/DashboardRoute.tsx` + `frontend/src/admin/styles/admin.css`.
- [x] Mini App loading-screen stabilization: unified startup lifecycle between `frontend/index.html` and `frontend/src/App.tsx`, removed polling race, and smoothed splash animation in `frontend/src/styles/global.css` (including reduced-motion profile).
- [x] Frontend-wide animation stabilization pass: unified motion tokens/easing in `frontend/src/styles/tokens.css`, softened keyframes and interaction feedback in `frontend/src/styles/animations.css` and `frontend/src/styles/components.css`, plus stronger reduced-motion guards for looping effects.
- [x] Focused motion polish for core UX zones: smoother interactions/transitions in `frontend/src/components/PlayerBar/PlayerBar.tsx` and `frontend/src/styles/global.css` for PlayerBar, TrackCardSheet, and Home cards/carousels (reduced jitter, calmer active states, better reduced-motion fallback).
- [x] Admin UI pass for secondary routes: KPI cards + sparklines for Users/Tracks/Complaints, plus live-toggle and loading/empty chart states for Metrics and Dashboard.
- [x] Admin dashboard statistics: backend `/api/v1/admin/dashboard/stats` with period aggregations (today/7d/30d), plus frontend stats block with KPI cards and top tracks list.
- [x] Admin tabs analytics expansion: track analytics (popular tracks + uploads timeline) and admin activity analytics (actions timeline + top admins) with period filters in `Tracks` and `Users` routes.

## Session Updates (2026-05-07) — iOS Redesign 2026 stage closure

- [~] **Radio hero waveform A/B pass (iteration 1 / style 1, candidate saved)**: в `./mini_app/radio` переработан visual baseline «основная волна + зеркальное отражение» для более минималистичного эфира (тоньше профиль, мягче контраст/blur, аккуратное fade-затухание отражения, адаптив desktop/mobile); вариант сохранён как кандидат через css-модификатор `rh-radio-hero-wave-bg--style1`; `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 2 / style 2)**: активирован более плотный и энергичный `live radio` стиль (`rh-radio-hero-wave-bg--style2`) с усиленной основной волной и явно читаемым зеркальным отражением (повышены opacity/контраст и глубина fade-маски); `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 2 / reflection fix + priority)**: `style2` зафиксирован как приоритетный; в `Waveform variant="radio"` волна переведена на baseline-отрисовку (не центр), чтобы зеркалирование реально читалось, плюс разделительная «waterline» и усиленный reflection-layer в hero; `npm run build` зелёный.
- [~] **Radio hero waveform A/B pass (iteration 3 / ambient-futuristic)**: добавлен необычный atmospheric-стиль `style3` с контурными кривыми (`repeating-radial-gradient`), glow-волной и отдельным зеркальным слоем/затуханием; сохранена структура «основная волна + отражение», `prefers-reduced-motion` соблюдён (анимации выключаются), `npm run build` зелёный.
- [x] **Temporary disable: Spotify account import (OAuth)** — backend endpoint `POST /api/v1/import/spotify_account` now returns 503; frontend `PlatformImportMethodModal` disables Spotify "login via account" action and keeps previous OAuth/import flow commented for fast restore; Spotify URL import remains active.
- [x] **Frontend haptic softening pass**: in `frontend/src/lib/telegram.ts` all existing interaction points keep their current calls, but Telegram haptic now prefers `selectionChanged` (fallback `impactOccurred('light')`) and browser vibration fallback is reduced to near-minimal pulses so feedback is barely noticeable.
- [x] **Frontend startup watchdog for infinite splash**: `frontend/src/App.tsx` init flow now has a guarded `try/finally` + 9s watchdog timer that forces app bootstrap completion (`setIsInitialized(true)` and auth fallback) if init network calls stall, preventing permanent loading screen.
- [x] Frontend performance pass (GPU/CPU): adaptive `ds-perf-lite` profile auto-enabled for coarse-pointer/low-spec devices, reduced global glass blur/saturation tokens, disabled expensive decorative layers/looping effects (`glass` noise/highlight, player glow, nav glow, queue EQ, video pulse), and throttled `BeatPulse` updates to ~20 FPS; `npm run build` green.
- [x] Playback hotfix: для SoundCloud `stream` recovery теперь считает `HTTP 502` (кейс `transcoding_manifest_404` по всем форматам) восстановимым и запускает fallback/replace трека вместо немедленного фейла `502`; добавлен regression-тест `test_recovery_handles_soundcloud_502_as_recoverable` в `tests/app/api/v1/tracks/test_playback.py`.
- [x] **Stage E (Chat/TrackCardSheet) — visual rewrite**: ChatList rows wrapped in `LongPressMenu` (mute/pin/unpin/mark-unread/delete) with monochrome icons; ChatBubble переведён на `m.div` со spring-scale (own send) / fade-up (incoming), реакции через `MorphIcon` + `LongPressMenu`; ChatView rewrite — `glass--liquid` sticky header с `MotionPress`/`MorphIcon`, `AnimatePresence` для menu dropdown, локализация всех hardcoded строк (`redesign.tracks.*`); ChatsView large-title sticky header; TrackCardSheet — drag-down close (threshold 100 px), все action-buttons на `MotionPress` + `MorphIcon`. CSS: `frontend/src/styles/redesign-tracks.css`.
- [x] **ChatView WS-dedup + DevPanel вынос**: activity-poll и message-poll теперь fallback (skip при `isWSConnected()`), интервалы 4s/8s; ~210 строк inline-styled DevTools вынесены в `frontend/src/components/Chat/ChatDevPanel.tsx` (DEV-only через `import.meta.env.DEV`), стили — в `redesign-tracks.css` (`.re-chat-dev-*`).
- [x] **Stage B (Onboarding) — stories-style transitions**: `AnimatePresence mode="wait"` + direction-aware variants через `directionRef` (forward/backward по stepIndex), `useReducedMotion` → opacity-only. Все интерактивные элементы (artist cards, mood/genre chips, calibration play/like/dislike/skip, footer Skip/Next, OnboardingGenreScreen preview) переведены на `MotionPress`; `MorphIcon` для pause-overlay и heart (filled при like). Inline-стили заменены классами `.re-onb-*` в `frontend/src/styles/redesign-nav.css`.
- [x] **Stage A (FullscreenLyrics) — Apple Music polish**: добавлен sticky header с маленькой обложкой через `BeatPulse` (bpm от трека, active=isPlaying) + meta-блок (title/artist) + close-кнопка на `MotionPress`. Playback controls (prev/play/next) на `MotionPress` + `MorphIcon` (`pause`/`play` filled). Стили в `frontend/src/styles/redesign-player.css` (`.rp-now-fl-*`).
- [x] **i18n**: новые ключи в `frontend/src/locales/i18n_extra2_{ru,en}.json` под `redesign.tracks.*` (chat menu, chat header/status, chat empty/divider, TrackCardSheet close, message reactions).
- [x] **Final acceptance**: `npx tsc --noEmit` — clean; `npm run build` — clean (vite + bundle-hygiene + admin-bundle), PWA precache 33 entries.
- [x] **Stream 2/3 polish (Stage D / I)**: ProfileView (tabs+settings → MotionPress, локализованы 'profile.tabProfile/Import/Complaints'), PlaylistsView (back/share/copy/close/share-row/create-playlist → MotionPress), LikedView load-more → MotionPress, ListenerStats period chips → MotionPress, OfflineList (clear-all + play + remove → MotionPress), HistoryList (retry + play row → MotionPress), UploadStepDetails (artist-mode + lyrics-trigger → MotionPress), UploadComboBox (toggle/items/create → MotionPress).
- [x] **Stage F (Artist views) + cross-cutting motion polish**: ArtistView — back/avatar/follow/snippet/source-tabs/admin-actions/bio-toggle/bio-more/catalog-cards/similar-arrows/similar-cards/listeners-toggle переведены на `MotionPress` + `MorphIcon` для play/pause превью, локализованы `redesign.artist.stopPreview/listenSnippets/sourcePlatform`; ArtistCatalogReleasePanel + ArtistAvatarViewer — back/close на `MotionPress`; AuthorView — back/follow на `MotionPress` + `Icon`, эмодзи `'👤'/'‹'/'✓'/'+'` заменены `Icon` (`user`/`chevron`/`check`/`bell`), inline-стили вынесены в CSS, hardcoded строки локализованы (`author.*`, `common.back`). Подмазаны pre-existing TS errors в AlbumView/PlaylistView/ExternalAlbumView/ExternalTrackView/GenreView (`return () => setBackButton(false)` → корректный void cleanup) и `'genre'` → `'genre_mix'` в `usePrefetchTracks`.
- [x] **Stage A overlays + Equalizer + Settings + Comments + Auth**: LyricsPanel (action-row + redefine/auto choice grids на `MotionPress`, локализация `lyrics.detectAuto/enterManually/redefineHeader/redefineTextOnly/redefineWithTiming/redefineNeedsAudio`), LyricsEditor (cancel/back/undo/seek-±5/play-pause/save-text/save-sync на `MotionPress` + `MorphIcon`), Equalizer (header chip/reset/close + preview-toggle + track-picker + presets на `MotionPress` с `MorphIcon` для play, локализация `equalizer.*`), SettingsSheet (back/close/EQ/openInBrowser/installAsApp/aboutApp/logout/test-sound/test-haptic на `MotionPress`), ComplaintModal (close/mode-toggle/submit на `MotionPress`), CommentCard (reply/menu/vote/delete/pin/hide/hideForMe на `MotionPress`), CommentInput (send на `MotionPress` с локализацией placeholder), CommentSection (reply-cancel на `MotionPress`), TelegramAuth + EmailAuth (все кнопки на `MotionPress`, эмодзи `✓` убран из success-icon). Pre-existing синтаксические ошибки `)` после `showIsland({...})` в TrackCard.tsx и TrackCardSheet.tsx исправлены, лишние `toast` deps в useCallback убраны.
- [x] **CSS уборка**: `redesign-artist.css` (`.rf-artist-snippet-wrap/btn/audio`, `.author-loader`, `.author-section-header`); `global.css` (`.eq-reset-confirm-label`, `.le-fs-save-btn`, `.lyrics-choice-back`, `.lyrics-choice-btn--disabled`); `i18n_extra2_{ru,en}.json` JSON-syntax bug `}` → `},` перед `"achievements": {}` пофикшен.
- [x] **Final acceptance (batch 2)**: `npx tsc --noEmit` — clean; `npm run build` — clean.
- [x] **Search screen blank-state fix**: восстановлен `SearchView` с discover empty-state (`/recommendations/discover`), табами `All/Tracks/Artists/Playlists`, и рендером результатов каталога + внешних источников; проверено через `npm run build`.
- [x] **Search discover genres polish**: `GET /recommendations/discover` теперь отдает `cover_key` для genre cards (по top-track в жанре), `SearchView` использует cover + визуальный fallback, блок `Ваши жанры` приведен к общему UI-стилю.
- [x] **Genre click search correctness**: добавлен явный `genre`-фильтр в `GET /api/v1/tracks` (route/service/repository), `SearchView` при клике по жанру передает `genre` в `api.getTracks`, чтобы выдача шла по жанру, а не только по title/artist.
- [x] **Search: dedicated Genres selector tab**: добавлена вкладка `Жанры` в `SearchView`, подгрузка каталога жанров через `GET /api/v1/tracks/genres`, и выбор жанра из вкладки с переходом к выдаче по `genre`-фильтру.
- [x] **Search genres UX + correctness finalization**: при клике на жанр активируется вкладка `Жанры`, в ней отображается счетчик `N треков в жанре`, и список треков этого жанра; в жанровом режиме отключено подмешивание `searchSuggest`-треков, чтобы не попадали нерелевантные результаты.
- [x] **Search genres stability + scalable list UX (2026-05-07)**: в `SearchView` жанровый режим изолирован от текстового поиска (защита от out-of-order ответов), добавлены алфавитная сортировка жанров, отдельный поиск по жанрам и поэтапная подгрузка (`Показать еще`) вместо моментального рендера всего списка чипов.
- [x] **Track card waveform + seek smoothness (2026-05-07)**: волна убрана из `PlayerBar` (нижнее состояние), в `TrackCardSheet` показывается только в открытой карточке и только при `isPlaying`; `WaveformBar` переведен на clip-based плавное заполнение прогресса; seek-индикаторы в `PlayerBar`/`TrackCardSheet` сглажены и убран визуальный «шлейф» у thumb; `npm run build` зеленый.
- [x] **PlayerBar volume quick entry (2026-05-07)**: в мини-плеер добавлена отдельная точка входа `volume` (иконка `volume-off/low/high`) с popover-слайдером `0..100%`, чтобы регулировать громкость без открытия карточки трека; закрытие по клику вне/`Esc`; стили в `frontend/src/styles/components.css`; `npm run build` зеленый.
- [x] **PlayerBar volume UX follow-up (2026-05-07)**: popover громкости переведен в вертикальный формат (вертикальный слайдер + компактный стек), а кнопку громкости перенесена ближе к транспортным контролам (перед like), чтобы доступ был быстрее в мини-плеере; `npm run build` зеленый.
- [x] **Hide YouTube tracks from public surfaces (2026-05-07)**: backend filters now exclude `source_platform/imported_from == "youtube"` from track lists/search/recommendation pools/playlists/likes/library and `TrackService.get_track` returns hidden for YouTube entries, so existing DB records are no longer shown in Mini App/API public flows.
- [x] **TrackCard: remove uploader block (2026-05-07)**: удалён блок «кто добавил трек» (аватар+ник) из `TrackCardSheet`; в backend `TrackCardResponse` больше не возвращает `author`, `CardService` перестал подгружать пользователя для карточки; обновлены frontend типы `TrackCardResponse` и schema-тесты `tests/app/schemas/test_card.py`.
- [x] **PlayerBar progress sync fix (2026-05-07)**: устранён рассинхрон верхней seek-линии и нижней glass-заливки в мини-плеере — оба слоя теперь используют единый `--progress` без двойного сглаживания, фон `#player-bar::after` выровнен по геометрии thumb (`--pb-fill` с компенсацией половины thumb), убраны рывки от hover/tap изменения толщины seek, добавлены согласованные WebKit/Firefox стили трека/прогресса/ползунка; `npm run build` зелёный.
- [x] **Ultra-smooth seek animation pass (2026-05-07)**: `PlayerBar` и `TrackCardSheet` переведены на локально сглаженное обновление прогресса через `requestAnimationFrame` + `getPreciseTime()` (плавнее fill/thumb/time без ступенчатости). Для `tcs-seek` увеличена зона нажатия (расширенный hit-area по вертикали) без визуального утолщения трека; сборка `npm run build` — зелёная.
- [x] **Radio disc swipe + playback-only motion (2026-05-07)**: `RadioView` теперь анимирует круговую обложку только при фактическом воспроизведении, поддерживает свайп влево/вправо в radio mode для переключения треков и slide-переход диска; `npm run build` зелёный.
- [x] **Radio hero wave background polish (2026-05-07)**: для `./mini_app/radio` в `rh-radio-hero__inner` добавлен размытый full-width wave-layer на базе `Waveform` (двойной слой + градиент), визуально по аналогии с волной карточки трека; `npm run build` зелёный.
- [x] **Radio hero wave expression pass (2026-05-07)**: усилил радио-визуал волн — multi-layer (`Waveform` x3) с разной частотой/плотностью баров, более контрастным градиентом, live-режимом `rh-radio-hero-wave-bg--live` и мягким drift/breathe движением для более «эфирного» радио-ощущения; `npm run build` зелёный.
- [x] **Radio hero waveform structure correction (2026-05-07)**: по фидбеку переделан фон радио в схему «одна основная волна + её отражение» (mirror), убраны лишние слои, обновлены частота/плотность формы (`bars=30`) и адаптивная высота через `clamp` для desktop/mobile; `npm run build` зелёный.
- [x] **Radio waveform visual-only refinement (2026-05-07)**: убрано любое «качание» фона и переделан именно силуэт волны для радио (`Waveform variant="radio"`: более собранный профиль с центральным акцентом, статичный render + mirror reflection), адаптив сохранён для desktop/mobile; `npm run build` зелёный.
- [x] **Radio next-track compact block (2026-05-07)**: блок настроений в `RadioView` деактивирован через TODO-комментарии, вместо него на `./mini_app/radio` показывается компактная карточка «Следующий трек» с обложкой, названием и артистом из очереди `PlayerContext`; `npm run build` зелёный.
- [x] **Radio paused pulse stability (2026-05-07)**: `BeatPulse` получил явный `data-beat-active`, а radio disc отключает `transform/transition` в paused-состоянии, чтобы обложка не дёргалась при паузе; `npm run build` зелёный.
- [x] **Mix views i18n + API typing cleanup (2026-05-07)**: `DailyMixView`/`WeeklyMixView`/`UserChoiceView`/`WeeklyTopView` переведены с hardcoded share-строк на `useTranslation` (`redesign.library.*` + `redesign.home.mixShareAria`), а в `frontend/src/lib/api.ts` убраны inline response-shapes в пользу типизированных контрактов `UserListeningStatsResponse`, `AdjacentTracksResponse`, `TrackQueueResponse`, `HomePageResponse` из `frontend/src/types/api.ts`.
- [~] **Endless radio anti-loop hardening (2026-05-07)**: переработан `build_radio_queue` в PrivateCore (seed-lock старт, микс unseen/favorite/rediscovery/similar, анти-повтор треков по недавней истории, cooldown артистов), backend radio cache теперь учитывает `exclude_ids` fingerprint, добавлен skip-guard `1 req/sec` с возвратом last queue для `GET /api/v1/recommendations/radio` и `GET /api/v1/tracks/{id}/radio`, лимит `exclude_ids` расширен до 200.
- [~] **Endless radio hardening follow-up (2026-05-07)**: добавлены Prometheus-метрики `radio_requests_total`, `radio_guard_hits_total`, `radio_queue_size` в `app/core/observability.py` + интеграция в `RecommendationService.get_radio` и `RadioService.build_queue`; добавлены unit-тесты `test_get_radio_guard_uses_last_queue` и `test_get_radio_cache_key_depends_on_exclude_ids` (прогон backend service-suite временно блокируется существующей SQLite DDL ошибкой `unrecognized token ":"` в test fixture setup).
- [x] **Endless radio phase-2 (2026-05-07)**: реализован A/B tuning радио через DB-настройку `recsys.radio_tuning` (варианты A/B, split по user bucket) с admin API `GET/PUT /api/v1/admin/system/radio-tuning`; tuning проброшен в PrivateCore (`RadioTuning`, `normalize_radio_tuning`, параметризованный `build_radio_queue`). Dashboard получил KPI-блок по радио через Prometheus (`radio_requests_5m`, `radio_guard_hits_5m`, `radio_queue_size_avg_5m`), плюс устранён SQLite test blocker (`genre_mix_overrides.track_ids server_default` без `::jsonb`) — backend service tests снова зелёные.
- [x] **Endless radio mix: explicit likes + dislikes (2026-05-13)**: `build_radio_queue` принимает `liked_track_ids` / `disliked_track_ids` (явные лайки в favorite/rediscovery без порога «2 полных прослушивания», дизлайки отфильтрованы), tuning-параметр `explicit_like_boost`, порядок round-robin бакетов unseen→favorite→similar→rediscovery; дефолты `RadioTuning` (cooldown 3h, `unseen_boost` 0.28); backend `get_radio` пробрасывает prefs; admin `RadioTuningPayload`; bump `RECSYS_ALGORITHM_VERSION`. Тесты PrivateCore `test_recommendation_engine.py`.
- [x] **Endless radio: меньше повторов одних и тех же треков (2026-05-13)**: `get_radio` объединяет клиентский `exclude_ids` с Redis-сессией радио (`radio:session`), передаёт объединённый набор в `get_candidate_tracks` / stratified и в фичи для `build_radio_queue` (раньше кандидаты тянулись топ-200 без exclude — одни и те же хиты); cap `_RADIO_MERGED_EXCLUDE_CAP`, буфер сессии 48; фронт: `excludeIds` последние 60 id, Set до 80. `recommendation_service.py`, `PlayerContext.tsx`.
- [x] **Stats TODO close + i18n/typing batch (2026-05-07)**: TODO-пункт про отдельную страницу статистики артиста (`/artist/:id/stats`) закрыт как выполненный; в `RadioView` и `SearchView` убран оставшийся hardcoded text в пользу i18n-ключей, а в `frontend/src/lib/api.ts` ещё один пакет inline response-типов вынесен в именованные интерфейсы `frontend/src/types/api.ts` (`StatusResponse`, `OkResponse`, `MessageResponse`, `AuthConfigResponse`, `LinkStatusResponse`, `EqSettingsResponse`, `PrefetchPolicyResponse`, `ConversationRefResponse`, `SearchUserItem` и др.).
- [x] **i18n + API typings batch 2 (2026-05-07)**: `GenreMixView` очищен от `defaultValue`/RU fallback-строк в `t(...)` (чистые i18n-ключи), а в API-клиенте вынесены ещё inline-контракты в `frontend/src/types/api.ts` (`AdminManifestResponse`, `MyComplaintsResponse`, `UserPresenceResponse`, `ChatPresenceResponse`, `OnboardingGenrePreviewResponse`, `OnboardingArtistItem`, `SmartSkipResponse`, `RadioResponse`) с подключением в `frontend/src/lib/api.ts`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n + API typings batch 3 (2026-05-07)**: в `ProfileView` убраны fallback-строки у `t(...)` для вкладок/настроек (`profile.tabProfile`, `profile.tabImport`, `profile.tabComplaints`, `profile.openSettings`) и добавлены недостающие ключи в `frontend/src/locales/{ru,en}.json`; в `api.ts` закрыт оставшийся inline response для `getFollowedArtistsList` через новый `FollowedArtistListResponse` в `frontend/src/types/api.ts`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 4: LegalView localization (2026-05-07)**: `frontend/src/views/LegalView.tsx` полностью переведен на i18n-ключи без hardcoded RU текста (заголовки разделов, абзацы, пункты списков и подписи ссылок), добавлены ключи `redesign.legal.*` в `frontend/src/locales/i18n_extra2_{ru,en}.json`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 5: ChatView fallback cleanup (2026-05-07)**: в `frontend/src/views/ChatView.tsx` удалены все `defaultValue` и fallback-строки у `t(...)` (last-seen, saved-hint, block/unblock, empty/unread labels), оставлены только i18n-ключи `redesign.tracks.*`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 6: NowPlayingView fallback cleanup (2026-05-07)**: в `frontend/src/views/NowPlayingView.tsx` удалены fallback-строки из `t(...)` для player labels/aria/tabs/about (оставлены только `redesign.player.*` ключи); `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **i18n batch 7: TrackCard fallback cleanup (2026-05-07)**: в `frontend/src/components/TrackCard/TrackCard.tsx` удалены fallback-строки у `t(...)` в меню long-press (`like/unlike`, `addQueue`, `share`, `shareFail`, `longPressQueued`) — оставлены только i18n-ключи `redesign.tracks.*`; `npm run tsc -- --noEmit` и `npm run build` зелёные.
- [x] **Disable track downloading in Mini App (2026-05-07)**: из `TrackCardSheet` удалена кнопка «Скачать» и связанная offline-cache логика (`downloadTrack/isCached/removeTrack`), а из `LibraryView` убрана вкладка «Скачанные» (`offline` tab + i18n keys `library.tabOffline`); `npm run build` зелёный.
- [x] **Profile: вкладка дизлайков (2026-05-07)**: `GET /api/v1/dislikes/{user_id}` — только для авторизованного владельца (`403` если id не совпадает с `current_user`), пагинация и `source` как у лайков; репозиторий `list_disliked_tracks`, `DislikeService.list_disliked` + collapse вариантов; фронт: `DislikedView`, вкладка `profile.tabDislikes` в `ProfileView`, клиент `getDislikedTracks`, ключи `redesign.library.disliked*`; тесты `test_dislikes.py` / `test_dislike_service.py`.

## Платформы — будущее

- **Гибридный плеер**: для платформ с официальными embed-виджетами реализовать `access_mode="official_embed"` - храним embed URL, отрисовываем `<iframe>` вместо нативного плеера, отключаем EQ. Приоритет: YouTube (требует TOS раздел 5.D).
- **VK Музыка**: OAuth уже реализован (`linked_accounts`, scope `audio`). Нужно добавить `VKStreamService` (получает HLS-URL через `audio.getById` с user OAuth token) и расширить `playback.py`. Отложено - российский сервис.
- **Яндекс Музыка**: нужен новый OAuth-провайдер (`Yandex OAuth`, oauth.yandex.ru) + неофициальный API-адаптер. Отложено - российский сервис.
- **YouTube TOS compliance**: согласно TOS YouTube раздел 5.D прямой API-стриминг запрещен. Долгосрочно: мигрировать на `access_mode="official_embed"` (iframe-embed), API-стриминг оставить только как dev/fallback.

## Sprint concurrency hardening (2026-04-22)

- Backend: миграция `0045_dedupe_unique_constraints` - partial UNIQUE на `tracks.sc_url WHERE sc_url IS NOT NULL` и на `(imported_from, external_id) WHERE external_id IS NOT NULL`, `Index` объявлены в `app/models/track.py:Track.__table_args__` (создаются и для тестовой SQLite-схемы)
- Backend: `scripts/dedupe_tracks.py` - pre-migration helper, dry-run по умолчанию, мерджим дубли по `sc_url` и `(imported_from, external_id)` с union-find и FK-redirect для likes/dislikes/playlists/track_artists/ track_lyrics/track_info/track_upload_meta/complaints/listen_events/ comments/lyrics_jobs/search_events/messages
- Backend: `SoundCloudService.import_or_get_track` переписан на `INSERT ... ON CONFLICT (sc_url) WHERE sc_url IS NOT NULL DO NOTHING RETURNING` + fallback `SELECT`; `external_import_worker` обернут в `try/except IntegrityError` на случай rolldown-сценария
- Backend: миграция `0046_add_lyrics_sync_source_name` - `track_lyrics.sync_source_name VARCHAR(50) NULL`, проброс через `LyricsRepository.create_or_update`, `LyricsResponse` schema, `_result_to_payload(getattr(gen_result, "sync_source_name", None))`
- Backend: `app/services/sc_semaphore.py` - Redis-based counting semaphore (sorted-set + Lua acquire) вокруг SoundCloud `search`/ `resolve_url`/`get_stream_info`, env `SOUNDCLOUD_GLOBAL_CONCURRENCY=4`
- Backend: per-track Redis lock в `lyrics_worker.generate_lyrics_task` (рефакторинг через outer wrapper + `_generate_lyrics_task_impl`), env `LYRICS_PER_TRACK_LOCK_TTL_SECONDS=300`; race-protected через `SET NX EX` + Lua-release-on-match
- Backend: `app/services/import_queue_dispatcher.py` - backpressure через статус `"queued"`, env `IMPORT_MAX_CONCURRENT_JOBS=10`, `IMPORT_PER_USER_MAX_CONCURRENT=2`, dispatcher loop запускается в WORKER_STARTUP. `ImportService.start_import` возвращает job с `status="queued"` если глобальный или per-user cap занят; `get_queue_position` для UI; `cancel_job` и `_get_active_job` понимают `"queued"`
- Backend: `app/services/lyrics_global_orchestrator.py` - единый pacer через `BLPOP lyrics:queue:default`, фичерфлаг `LYRICS_GLOBAL_ORCHESTRATOR_ENABLED=true`, заменяет per-job пейсинг в `import_lyrics_worker.process_import_lyrics_task` (legacy mode сохранен, активируется выключением флага). Global circuit-breaker на 5 подряд `captcha|pool_exhaust|exhausted` сигналов из proxy_pool
- Backend: API `GET /import/{id}/status` и `/import/active` возвращают `queue_position` для queued джобов
- Backend: `main.py` зарегистрировал воркеры `app.services.import_queue_dispatcher` и `app.services.lyrics_global_orchestrator`
- Frontend: `ImportView.tsx` - новая фаза `"queued"` с отображением `queue_position`, polling переключается между `queued <-> importing` без пересоздания интервала
- Frontend: `LyricsPanel.tsx` и `FullscreenLyrics.tsx` - admin-only debug-блок «Источник текста» / «Синхронизовал» в самом конце отображенного текста, гейтится через `getIsAdmin()`; CSS `.lyrics-debug-attribution` (минимализм, монохром, monospace)
- Docs: `docs/private-core-dependency-policy.md` пополнен таблицей опциональных полей `GenerateResult` (включая новый `sync_source_name` - PrivateCore-side требуется добавить поле, Backend уже forward-compatible через `getattr`)
- Tests: `test_soundcloud_service::test_import_or_get_track_dedup_via_unique_index`, `test_lyrics_worker::test_sync_source_name_propagates_to_repo`, `test_lyrics_global_orchestrator.py` (новый файл, 7 тестов на serialize/deserialize/process_one), `test_import_service` (3 новых теста на backpressure + queue_position + cancel queued), `test_import_lyrics_worker` autouse-фисктура форсит legacy режим

## Sprint multi-importer library (2026-04-22)

- Backend: миграция `0047_add_user_track_library` - many-to-many таблица `user_track_library (user_id, track_id, source, imported_at)` с composite PK + индекс `(user_id, imported_at)`. Backfill из `tracks.uploaded_by_id` чтобы существующие треки попали в библиотеку владельца
- Backend: `app/models/user_track_library.py` (модель) + `app/repositories/user_track_library.py` (`add` идемпотентен через `INSERT ... ON CONFLICT DO NOTHING`, `list_by_user`, `count_by_user`, `has`, `remove`)
- Backend: auto-link во всех flow создания трека - `external_import_worker.py` (после `import_or_get_track`, включая dedup-resolved случай), `import_worker.py` (telegram), `upload_service.py` (UGC). Идемпотентно - повторный импорт одной песни одним юзером не дублирует
- Backend: `GET /api/v1/users/me/library` - paginated, ORDER BY `imported_at DESC`, `playable_only` filter; `TrackService.list_library`, `UserTrackLibraryRepository.list_by_user` с JOIN
- Backend: `LyricsService._get_editable_track` - для `catalog_type='external_reference'` редактирование лирики только админом, для UGC оригинальный uploader (как раньше). Все методы `create_or_update`/`update_sync`/`delete_lyrics`/`redefine`/ `trigger_auto_generation`/`cancel_auto_generation` переведены на новую проверку
- Backend: defensive `LyricsRepository.get_by_track_id` skip в `lyrics_global_orchestrator._process_one` - закрывает race window между `_enqueue_to_global_queue` и моментом обработки (другой воркер мог уже сохранить лирику)
- Frontend: `api.getMyLibrary(page, size, playableOnly)` метод; `ProfileView` переключен с `getMyTracks` на `getMyLibrary`, пользователь видит и свои аплоады, и импортированные треки
- Frontend: `LyricsPanel` принимает `catalogType` prop, кнопки редактирования гейтятся через `canEdit = isExternalRef ? isAdmin : isOwner`. Все 4 точки ownership-gating обновлены. `TrackCardSheet` пробрасывает `catalog_type`, edit-pane lyrics-toggle кнопка скрыта для non-admin на external_reference
- Frontend: `ImportView` фаза `done` показывает «Треки добавлены в вашу библиотеку (профиль)»
- Tests: `test_user_track_library.py` (7 кейсов: idempotency, shared-by-two-users, ordering, remove, count, has), `test_external_import_worker::test_two_users_share_track_with_two_library_links`, `test_lyrics_service` (3 новых: external blocks owner, allows admin, ugc owner ok), `test_lyrics_global_orchestrator::test_process_one_skips_when_lyrics_already_in_db`

## Sprint admin / auth (2026-04-19)

- Frontend: синхронный `api.restoreSession()` в `main.tsx` до рендера - убирает раннюю гонку токена с AdminProvider/PlayerProvider
- Frontend: `AdminContext.tsx` гейтит `getAdminManifest()` на наличие токена и подписан на `app-auth-ready` + `i18n.languageChanged`; убран orphan-импорт `adminBundleUrl`
- Frontend: `App.init()` пропускает `api.authTelegram('')` при пустом initData (убирает 422 + 500ms ретрай в ngrok-режиме)
- Frontend: `connectWS(...)` вызывается сразу в `verifyTelegramCode` / `verifyMagicLink` / `verify2FA`, плюс диспатч `app-auth-ready`
- Frontend: `restoreSession()` восстанавливает `auth-user-id` из JWT `sub`, если он потерян - убирает «при обновлении просит код»
- Frontend: Suspense fallback с timeout-ом и retry в `App.tsx` (`RouteFallback`) - убирает «черный экран» при зависших lazy-чанках
- Frontend: i18n RU/EN для всей админки (`admin.`* namespace в локалях, `useTranslation` в `AdminApp`, `AdminShell`, всех auth-формах и routes)
- Frontend: `AuthGate` запускает `ensureCsrf` и `bootstrapMetadata` параллельно через `Promise.allSettled` и пытается `adminApi.refresh()` на старте - admin-сессия переживает reload без TOTP
- Frontend: `useAdminAuth.capabilities` наполняется из манифеста после успешного refresh - `useCapability` теперь работает
- Frontend: proactive refresh за 30 сек до expiry в `adminFetch`; при фейле refresh статус `'needs_login'` вместо `'unauth'`
- Frontend: `AdminShell` - часы вынесены в изолированный `<Clock />`, остальная панель не перерисовывается каждую секунду
- Frontend: refetchInterval поднят до 15-30 сек и `refetchIntervalInBackground: false` во всех админ-routes (Dashboard, Logs, Tasks, Metrics, Containers, Security, Settings, AudioCompute)
- Frontend: удален orphan-файл `frontend/src/admin/AdminDashboardView.tsx`
- Frontend: `?nosw=1` в URL разрегистрирует service worker (отладка на ngrok)
- Frontend: убран дублирующий `<Route path="/admin">` без `*` в `App.tsx` - nested `<Routes>` в `AdminApp` теперь корректно рендерит `DashboardRoute`
- Frontend: `adminApi.refresh()` и `adminApi.logout()` больше не шлют `body: {}` - backend теперь читает refresh token из httpOnly-cookie без 422 от валидации `AdminRefreshRequest`

## Sprint bugfix (2026-04-20)

- **(0)** Policy amendment: расширить "Source Attribution Exception" на lyrics / track-info провайдеров (`CLAUDE.md` + `docs/ai-boundary-policy.md`)
- **(1)** Track info: перенос из внешней кнопки внутрь `TrackCardSheet` (после блока «похожие треки»), DEBUG-refresh (admin), автозагрузка и polling
- **(2)** Track info worker: `/api/v1/tracks/{id}/info` зависает в `fetching` - stale-retry в сервисе, `asyncio.wait_for` timeout 90s в воркере, `fetched_at` отражает последнее состояние
- **(3)** `TrackCardSheet`: белая заливка прогресс-бара - CSS gradient с `--progress` + inline style на seek-input
- **(4)** `SettingsSheet`: кнопка «Назад» с label + Telegram BackButton + Esc
- **(5)** `TrackCardSheet`: крестик 44х44, safe-area-inset-top/right, не выходит за рамки
- **(6)** `TrackCardSheet`: «Перейти к автору» использует `track.artist` через `onOpenArtist`; ряд загрузчика переименован
- **(7)** Admin: `/logs/query` и `/metrics/range` возвращают `source_status` + `/system/observability` endpoint, banner в `LogsRoute` / `MetricsRoute`
- **(8)** Admin lyrics-jobs: индивидуальный cancel (inline-кнопка) + bulk `POST /tasks/lyrics-jobs/cancel-queued`; `queued` сразу переводится в `cancelled` в БД
- **(9)** Admin Artists: `DELETE /artists/{id}`, клик по имени - `/mini_app/artist/:id` (новая вкладка), fix даты через fallback на `created_at`, `updated_at` добавлен в `ArtistResponse`
- **(10)** Admin Tracks: existing `DELETE` + visibility-toggle + inline `<audio>` + открытие `/mini_app/track/:id`
- **(11)** Admin Users: ban/unban + `POST /users-ext/{id}/force-logout` (revoke admin sessions + Redis marker) + `POST /users-ext/{id}/message` (DM через `ChatService`/`MessageService`)
- **(12)** Lyrics: cache-hit с text-only при `with_sync=true` пре-сохраняет текст в БД и продолжает в audio-based sync flow
- **(13)** WS: `_is_ws_open()` guard + `try/except (WebSocketDisconnect, RuntimeError)` - ранний выход из `_broadcast_loop`
- **(14)** Lyrics: `LyricsResponse.source_name` (optional) для UI-attribution + `lyrics_provider_name` / `track_info_provider_name` env-flag selectors; алгоритмика остается в PrivateCore

## Playback variants / composition grouping (2026-04-29)

- `[x]` PrivateCore: `playback_variant_policy` (порядок платформ, tolerance)
- `[x]` Backend: `composition_group_id`, `PlaybackVariantService`, `build_track_response` / `dedupe_and_build_track_list`, `TrackResponse.playback_variants`, лайки/дизлайки по группе, комментарии по `variant_ids`, read-only stream fallback
- `[x]` Frontend: типы API, `LikesContext` по `playback_variant_track_ids`, переключатель источника в плеере
- `[x]` Tests: mock `catalog_only_lyrics_task.kiq` в `create_test_track` / `mock_taskiq` и в `test_upload_track_success`
- `[x]` `scripts/backfill_composition_groups.py` (stub)

## Home Menu Redesign - v2 (2026-05-04)

- `[x]` **ArtistFollowRepository**: `list_followed_artists(user_id, limit)` - `list[Artist]`
- `[x]` **Schemas**: `FollowedArtistItem`, `FollowedArtistListResponse` в `artist_follow.py`
- `[x]` **API**: `GET /api/v1/artists/followed` endpoint
- `[x]` **PrivateCore**: `build_genre_mixes()`, `GenreMixResult`, `MAX_GENRE_MIXES`, `GENRE_MIX_SIZE` в `recommendation_engine.py`; экспорт в `services/__init__.py`
- `[x]` **Backend**: `GET /api/v1/recommendations/genre-mixes` (endpoint + `RecommendationService.get_genre_mixes()`)
- `[x]` **Backend**: `GET /api/v1/recommendations/radio` - добавлен `exclude_ids` query param (max 30)
- `[x]` **RecommendationService.get_radio**: принимает `exclude_ids: list[int] | None`
- `[x]` **Schemas**: `GenreMixItemResponse`, `GenreMixesResponse` в `recommendation.py`
- `[x]` **global.css**: все Home v2 CSS-классы (greeting, quick-grid, carousel, artist-strip, genre-mix-card, player-radio-badge, top nav-indicator)
- `[x]` **api.ts**: `getFollowedArtistsList()`, `getGenreMixes()`, обновлен `getRadio(excludeIds?)`
- `[x]` **types/api.ts**: `FollowedArtistItem`, `GenreMixItem`, `GenreMixesResponse`
- `[x]` **HomeView.tsx**: полный редизайн - приветствие, quick-grid, genre mixes carousel, followed artists strip, секционные карусели треков по section_type
- `[x]` **BottomNav.tsx**: верхний индикатор (`.nav-btn__indicator`) для активного таба
- `[x]` **GenreMixView.tsx**: новый view `/genre-mix/:genre`
- `[x]` **App.tsx**: маршруты `/genre-mix/:genre`; lazy-import `GenreMixView`
- `[x]` **Icon.tsx**: добавлены иконки `radio`, `users-following`
- `[x]` **PlayerContext.tsx**: `radioMode`, `radioSeedTrackId`, `startRadio()`, `stopRadio()`; `playNext()` - авто-fetch при пустой очереди в radio-режиме; `played_ids Set` (max 50)
- `[x]` **RadioView.tsx**: переработан - кнопка «Запустить бесконечное радио», индикатор режима, история прослушивания
- `[x]` **PlayerBar.tsx**: `.player-radio-badge` при активном `radioMode`; клик - `/radio`
## Chats / Track Share (2026-05-04) [FROZEN — legal hold (149-ФЗ ОРИ)]

> Раздел заморожен: чаты/p2p-обмен сообщениями отключены до
> оформления юрлица и подачи в реестр ОРИ. Не трогаем код в
> рамках обычных задач, см. `docs/REGULATORY_DISABLED.md`.

- [x] Share track to chat ? modal picker in TrackCardSheet, send via api.sendMessage(..., { type: 'track_share', shared_track_id }), and shared-track bubble with Play in ChatBubble.
- [x] Chat share: albums and playlists (shared_album_id, shared_playlist_id) + updated Home track/artist card styling for .sound consistency (2026-05-04).

## Lyrics Roadmap

- [x] Add support for per-track lyrics translations (store translated text separately from original lyrics), including backend API/model + minimal language switch in lyrics UI (2026-05-06).
- [x] RU/EN brand switch for mini app: default '.звук', English '.sound' (loader, splash, auth, home, admin shell, static build sync) - 2026-05-04

---

## Future Features & Enhancements (Planned May 2026)

- [ ] **AI-Mood & Genre Tagging (v1)**
    - [ ] Автоматическое тегирование на основе анализа аудио (ComputeWorker).
    - [ ] Анализ метаданных и текста песен через LLM (определение настроения/жанра).
    - [ ] Хранение в Backend и отображение в UI.
- [-] **Listening Party (v2)** [FROZEN — legal hold (149-ФЗ ОРИ)]
    - [ ] Интеграция с чатами (создание комнат внутри групп).
    - [ ] "Демократичная очередь" (голосование за треки).
    - [ ] Улучшение UI и синхронизации.
    > Заморожено: зависит от чатов, которые отключены до оформления
    > юрлица и подачи в реестр ОРИ.
- [x] **Музыкальные профили и статистика**
    - [x] PrivateCore `user_top_policy` (per-window blend
      log(completed_listens) + log(likes), thresholds, limits).
    - [x] Backend `StatsService.get_user_top_tracks/genres`,
      агрегации в `ListenEventRepository`,
      `GET /api/v1/users/me/top?window=7d|30d|90d|all`.
    - [x] Frontend `api.getMyTop`, плитка «Ваш топ» в
      `MIX_SHORTCUT_TILES` (быстрые разделы Home),
      `MyTopView` `/my-top` с переключателем окон 7d/30d/90d/all.
    - [x] `aggregate_user_minutes_by_day` +
      `GET /users/me/listening-by-day?days=N` +
      `api.getMyListeningByDay`; bar-chart в `MyTopView` и
      встроенный sparkline в `ProfileStatsTab`.
    - [x] Полноценный таб «Статистика» в `ProfileView` (часы
      прослушивания, графика по жанрам, привязка `RecapShareCard`
      к реальным данным): `ProfileStatsTab` (период 7/30/365д,
      hero KPI, CSS genre bars, top-artists list, RecapShareCard с
      реальными минутами и обложками из `getMyTop`); кнопка входа
      через `ProfileActions` (`chart-bar` icon); i18n RU/EN.
- [x] **Динамические плейлисты**
    - [x] "Weekly Top 50" -- 2026-05-06: PrivateCore weekly_top_policy (rank_weekly_top_tracks, blend log(listens_7d)+log(likes_7d), WEEKLY_TOP_SCORE_VERSION); Backend RecommendationRepository.get_qualified_listens_7d_counts, RecommendationService.get_weekly_top_playlist with Redis cache (TTL 30 min), GET /api/v1/recommendations/weekly-top; Frontend WeeklyTopView (/weekly-top), api.getWeeklyTopPlaylist, WeeklyTopPlaylistResponse type, flame icon, Home quick-grid card.
    - [x] **«Забытые сокровища»** (лайкнутое давно, без прослушиваний в окне) — PrivateCore `forgotten_treasures_policy` (пороги лайка ≥21d, тишина ≥14d, `rank_forgotten_treasure_tracks`); Backend `RecommendationRepository.list_forgotten_treasure_rows`, `GET /api/v1/recommendations/forgotten-treasures` (JWT, per-user); Mini App `ForgottenTreasuresView` `/forgotten-treasures`, тайл в быстрых разделах после «Выбор»; prefetch context `forgotten_treasures`.
- [x] **PWA Offline Mode (v2) [High Priority]**
    - [x] PrivateCore `offline_policy` (allow-list по `access_mode`/
      `catalog_type`, лимиты на трек / на пользователя).
    - [x] Backend: `GET /api/v1/tracks/{id}/offline-eligibility`
      и заголовок `X-Offline-Allowed` на HLS-плейлистах,
      сегментах и progressive `/audio` (cached-from-S3 ветка).
    - [x] Service Worker (`vite-plugin-pwa`): `cacheWillUpdate`-
      плагин на `progressive-audio-cache` и `hls-segments-cache`
      отказывается записывать ответы с `X-Offline-Allowed: 0`.
    - [x] `offlineCache.downloadTrack` сначала вызывает
      `getOfflineEligibility`, проверяет server-флаг в ответе,
      применяет LRU-вытеснение по `cachedAt`.
    - [x] `TrackCardSheet`: пункт «Сохранить оффлайн» / «В оффлайне»
      (скрыт для `access_mode === 'third_party_stream'`),
      `isCached` индикатор, removeTrack для toggle.
    - [x] Авто-переключение плеера в cached-only при
      `navigator.online === false`: `PlayerContext.playNext`
      при offline (1) идёт по `manualQueueRef`, отбирает
      первый трек, который есть в кэше через
      `import('@/lib/offlineCache').isCached`, проигрывает
      его и снимает с очереди; (2) fallback к
      `_fallbackToCachedTrack` (любой кэшированный трек,
      кроме текущего/недоступных); (3) ветки radio/
      prefetch/adjacent НЕ запускаются (они зависят от
      сети и упали бы в catch). `playTrack` сам идёт через
      `getCachedAudioUrl` гейт.
- [x] **Anti-Abuse Fingerprinting**
    - [x] PrivateCore `abuse_fingerprint_policy`: `Decision`
      (PASS/THROTTLE/REQUIRE_CAPTCHA/LOCKOUT), `AbuseSignals`,
      пороги, `evaluate(signals, kind)`, retention/lockout
      константы.
    - [x] Backend: миграция `0088_abuse_events`,
      `AbuseEvent` модель, `AbuseSignalMiddleware`
      (`X-DS-Signal` capture), `AbuseSignalService.evaluate_event`,
      `abuse_fingerprint_adapter` для PrivateCore.
    - [x] Frontend: `lib/clientSignals.ts` (opaque hash:
      UA-class + webgl-vendor-class + timezone + language;
      без canvas-pixel/audio/fonts/biometrics);
      `ConsentBanner` показывается до первого расширенного
      сбора; `api.request` дополняет `X-DS-Signal` только при
      согласии.
    - [x] `AbuseEventRepository.recent_signal_counts` (sliding
      window) + `AbuseSignalService.evaluate_event` подключён
      в `auth.py /telegram` через `app/services/abuse_guard.py`
      (LOCKOUT → 423, REQUIRE_CAPTCHA → 429); миграция `0089`
      сидит cron `daily-abuse-events-pruner` `15 4 * * *`.


- [x] Public UI: admin inline editing for playlists/albums/tracks via non-admin routes with backend admin checks + reorder endpoints (2026-05-05).
- [x] Frontend: fixed share copy toast layering above share modal for track/album/playlist (z-index via --z-toast, 2026-05-05).
- [x] Frontend: TrackCardSheet now resolves album edit/share via fallback track.album_id (for mixes/playlists where card.album may be empty), 2026-05-05.
- [x] Frontend: share copy toasts can render at top (position=top) to avoid overlap with share modal; admin flag fallback from JWT claim is_admin in getIsAdmin, 2026-05-05.
- [x] Frontend: Apple-like .звук splash typography + loading animation; edit UI gates in TrackCardSheet simplified to admin/debug/dev for mix album editing on Home, 2026-05-05.
- [x] Frontend: ArtistView now shows a prominent monthly unique listeners KPI card in artist header (always visible with API fallback), 2026-05-05.
- [x] Frontend: ArtistView monthly listeners moved to compact inline text under artist avatar/name with new `users-listeners` SVG icon, 2026-05-05.
- [x] Frontend: Home greeting now shows only day/evening format (`Добрый день|вечер`) with optional user name (`| {{name}}`) and fallback without name, 2026-05-05.
- [x] Frontend: Home featured card now has a clearer right-side `Play` pill button near the upper-right area for explicit playback affordance, 2026-05-05.
- [x] Backend+Frontend: server-side genre-mix overrides (DB table + API PUT /recommendations/genre-mixes/{genre}) and hybrid track search in album/playlist/mix editors; removed local-only mix persistence, 2026-05-05.
- [x] Admin+Public artists: added batch AI prompt/import for artist supplemental text, switched artist card priority to Platform supplemental content, and temporarily commented out Yandex tab/UI in ArtistView, 2026-05-05.
- [x] Genre mix page now loads by exact endpoint GET /api/v1/recommendations/genre-mixes/{genre} (with override fallback), fixing lost edits after reload on /mini_app/genre-mix/:genre, 2026-05-05.
- [x] Frontend: fixed Profile settings feedback test in Telegram Android by hardening haptic fallback (WebApp + navigator.vibrate) and increasing audible UI test sound baseline, 2026-05-05.
- [x] Frontend: wired haptic+tap sound to regular Profile/Settings UI actions (tabs, profile actions, edit/save/cancel, toggles), not only feedback test buttons, 2026-05-05.
- [x] Frontend: improved Telegram Android haptic reliability (`selectionChanged` -> `impactOccurred` fallback + throttled `hapticTick`) and added micro-vibration ticks for EQ/track-volume sliders; regenerated deeper, neutral UI feedback sounds, 2026-05-05.
- [x] Admin compute: lyrics + generic compute job queue priority and worker pin, in-flight reassignment (lease release), API + Audio Compute UI; ComputeWorker treats 404 on result/fail as abandoned job (2026-05-05).
- [x] Frontend UI stability pass: removed nested interactive cards in `HomeView` (no `button` inside `button`), throttled carousel arrow scroll updates via `requestAnimationFrame`, added TrackCardSheet stale-request guard for fast track switching, and included safe-area bottom inset in `.tcs-sheet` padding (2026-05-06).
- [x] Mini App: fixed artist navigation regressions (followed artist opens artist card, tabs close active artist/author overlay) and upgraded Artist `Similar` section to photo cards with horizontal slider + arrow controls (2026-05-06).
- [x] Activation improvements (phase 2, 2026-05-06): backend persists onboarding activation timestamps (`auth_first_seen_at`, `first_play_at`), computes server-side `ms_from_auth_server`, and aggregates activation events in Redis for funnel metrics.
- [x] Admin dashboard (2026-05-06): added activation funnel endpoint `/api/v1/admin/dashboard/activation-funnel` and KPI cards for auth->first-play time, onboarding completion rate, skip rate, and first-session plays.
- [x] Onboarding UX (2026-05-06): resumable draft state in localStorage, feature-flag-aware smart skip (`feature.onboarding.smart_skip_enabled`), neutral calibration "skip" option, and import-progress CTA to listen to already imported tracks immediately.

- [x] Recsys: catalog station + album co-artist overlap weights in PrivateCore (`similarity_signal_policy`), `UserPrefs.similar_artist_weights`, hybrid `/artists/{id}/similar`, station-neighbor pool for `/recommendations/similar/{track_id}` (2026-05-07).

## Mini App iOS-redesign / поток 2 (прогресс)

- [x] **Stage H (recap / achievements)** — 2026-05-07: `RecapStoryStage` (9 слайдов, auto-advance, long-press pause, tap-зоны), `RecapView` + `/recap?tab=achievements` → `AchievementsView`, share sheet + `RecapShareCard` (9:16, TODO на реальный export без новых npm), `redesign-recap.css`, `getRecapSnapshotMock()` + `redesign.recap.*` в `i18n_extra2_*`.
- [~] **Stage D (library): поиск, медиатека, лайки, плейлисты** — 2026-05-07: `redesign-library.css`, `SearchView` (чипы фильтра сущностей, motion), `LibraryView` (tabs + layoutId, daily mix `MotionPress`), `LikedView` (сортировка, чипы `MotionPress`, sticky-шапка), `PlaylistsView` (сетка, `LongPressMenu`, поток «поделиться» с экрана списка), ключи `redesign.library.*` в `i18n_extra2_*.json`. Дальше: polish профиль/настройки, Stage F (artist shell), отдельные коммиты после `tsc`/`build`.

- [x] **Cross-cutting motion polish (batch 3)** — 2026-05-07: финальный проход MotionPress/MorphIcon по
  `AchievementsView` (плитки достижений), `Notifications/NotificationBell` + `NotificationList` (колокольчик,
  пункты меню, кнопки строк, more-vertical, close), все Import-модалки (`PlatformImportMethodModal`,
  `SoundCloudPlaylistUrlModal`, `VkMusicUrlModal`, `SpotifyUrlModal`, `YandexMusicUrlModal`) и `ImportView`
  (selectAll/deselectAll/cancel, queued/importing/done, cancel-confirm dialog), `Chat/VoiceRecorder` +
  `VoicePlayer` (cancel/play/preview/send + waveform speed), `Settings/AccountDangerZone` и
  `Settings/OAuthImportAccounts`. Inline-стили `style={{padding,gap,flex,...}}` вынесены в новые классы
  `rf-import-*`, `settings-danger-zone__*`, `settings-badge--clickable` (`redesign-artist.css`, `global.css`).
  TS clean (`npx tsc --noEmit`), `npm run build` зелёный, hygiene + admin-bundle проверки прошли.

- [x] **Micro-polish pass (batch 4)** — 2026-05-07: `OnboardingImportStep` полностью переведён с plain `<button>`
  на `MotionPress` (карточки источников, CTA в `empty/done/select/queued/importing`, оба confirm-модала), inline
  стили заменены классами `onboarding-import-*` в `global.css`; в `admin/routes/DashboardRoute` tick-кнопки
  metric slider также переведены на `MotionPress` (`icon` + `selection`). Проверки: `npx tsc --noEmit`, `npm run build`.

## Session Updates (2026-05-08)

- [x] **HorizontalSnap compact centering on desktop (2026-05-08)**: в `HorizontalSnap` добавлен флаг `h-snap--compact` для кейсов без реального overflow, а в shared-стилях на desktop fine-pointer (`min-width:768px`) короткие карусели автоматически центрируются (`justify-content:center`) для более аккуратного вида при малом числе карточек.

- [x] **HorizontalSnap smart dots (2026-05-08)**: в `HorizontalSnap` точки пагинации теперь считаются от реального числа страниц прокрутки (`scrollWidth/clientWidth`) и ограничены максимумом в 4; при 1 странице точки скрыты, при 2–4 показывается точное число, при >4 — агрегированный индикатор из 4 точек с корректным активным состоянием при скролле.

- [x] **Home desktop carousel spacing fix (2026-05-08)**: для `HomeView` убран лишний full-width wrapper у карточек «Миксы по жанрам», а в `redesign-home.css` desktop fine-pointer snap-элементы (`.rh-home-h-snap`, `.rh-home-artist-snap`) переведены на `width: max-content` вместо viewport-width, чтобы исчезли большие пустоты в секциях «Миксы по жанрам», «Продолжить слушать», «Недавно слушали» и ниже; `npm run build` зелёный.

- [x] Исправлены битые UTF-8 последовательности и восстановлены русские строки в `TODO.md`
  (блок Mini App UI, backlog «Home recommendations», секция «Платформы — будущее»);
  у пункта «Frontend: отдельная страница статистики» унифицирован формат статуса `[x]` (без лишних backticks).

- [x] Динамический плейлист **«Забытые сокровища»**: PrivateCore `forgotten_treasures_policy`, Backend
  `GET /api/v1/recommendations/forgotten-treasures`, Mini App `/forgotten-treasures` + prefetch context
  `forgotten_treasures`; pytest (PrivateCore ranking + API), `npm run build` зелёный.

- [ ] **Техдолг: полный прогон качества после серии изменений (2026-05-08)** — довести до конца и зелёного CI:
  `make test` (или `poetry run pytest -v`), `make lint` (ruff + black --check + mypy по `app/`),
  `python scripts/check_docs_sync.py`. Частичный прогон `pytest` до прерывания уже показывал несколько падений —
  после полного прогона зафиксировать список упавших модулей и закрыть регрессии.

## Session Updates (2026-05-10)

- [x] **Admin «Удалённые пользователи» вкладка**:
  `AdminRepository.list_deleted_users` (фильтр `deleted_at IS
  NOT NULL` + search), `AdminService.list_deleted_users /
  restore_user / hard_delete_user_now` (последний делает то же,
  что `AccountDeletionService` для одного юзера: purge
  `admin_actions_log`, `users.hard_delete`, S3 avatar cleanup
  best-effort). Эндпоинты `GET /api/v1/admin/users/deleted`,
  `POST /api/v1/admin/users/{id}/restore`,
  `DELETE /api/v1/admin/users/{id}/forever` (с rate-limit
  10/min на forever). Frontend: `adminApi.listDeletedUsers /
  restoreUser / hardDeleteUserForever`; в `UsersRoute`
  `AdminRangeSwitch` со значениями `All / Deleted`, в строках
  Deleted-режима — кнопки «Восстановить» и «Удалить навсегда»
  (с confirm-диалогом); `active/banned` фильтр прячется в
  Deleted-режиме.

- [x] **Track soft-delete + корзина (общий механизм, не только при
  удалении профиля)**: миграция `0087` (`tracks.deleted_at`,
  `deleted_by_id` SET NULL → users, `deleted_reason`, индекс
  `ix_admin_actions_log_user_id`, seed cron `daily-track-hard-delete`
  `0 4 * * *`); `Track` модель + `TrackRepository`
  (`delete_by_owner` теперь soft, `restore_by_owner`,
  `admin_soft_delete`, `admin_restore`, `list_user_trash`,
  `list_admin_deleted`, `list_hard_delete_candidates`,
  `hard_delete_track`); `TrackService` (restore, list_my_trash);
  `track_lifecycle_adapter` для PrivateCore-policy
  (контракт: `TRACK_HARD_DELETE_BATCH_LIMIT`,
  `should_hard_delete_track`, `grace_period_seconds`,
  `valid_track_delete_reasons`); новый
  `TrackHardDeleteService` + `track_hard_delete_worker.py`
  (S3 cleanup HLS-prefix/cover/video/file_key, ES delete,
  audio_blob ref release — всё перенесено из eager-cleanup
  в cron). User API: `DELETE /api/v1/tracks/{id}` теперь soft;
  добавлены `POST /api/v1/tracks/{id}/restore` и
  `GET /api/v1/tracks/me/trash`. Admin API: `AdminService.delete_track`
  тоже soft (по умолчанию `reason=admin`); добавлены
  `GET /api/v1/admin/tracks/deleted`,
  `POST /api/v1/admin/tracks/{id}/restore`,
  `DELETE /api/v1/admin/tracks/{id}/forever` (точечный hard).
  Frontend: новый `TrashView` (`/trash`) + ссылка из
  `SettingsSheet` («Корзина треков»); `api.getMyTrash`,
  `api.restoreTrack`, `api.getDeletionStatus`;
  `adminApi.deleteTrack(reason)`, `restoreTrack`,
  `hardDeleteTrackForever`, `listDeletedTracks`; обновлены
  i18n `trackCard.deleteConfirm` (упоминание корзины).

- [x] **Доводка удаления аккаунта (152-ФЗ ст.14/21)**:
  `AccountDeletionService.hard_delete_expired_users` чистит
  `admin_actions_log` по `user_id` (PII в `ip` и `meta`); треки
  пользователя НЕ трогаем (только `tracks.uploaded_by_id → NULL`
  как было в 0078). Эндпоинт `GET /api/v1/users/me/deletion-status`
  для countdown в UI; `AccountDangerZone` обновлён: при `pending`
  показывает обратный отсчёт grace-периода и кнопку «Отменить
  удаление». Тесты: `test_track.py` (soft_delete/restore/trash/
  candidates), `test_account_deletion_service.py` (admin-log
  purge + tracks остаются).

- [x] **Legal docs sync**: `LEGAL.md` секция «Удаление аккаунта и
  контента»; `docs/legal/PRIVACY_POLICY.md` §7.1 (аккаунт, треки
  не возвращаются автору) и §7.2 (корзина треков, grace per-reason).

- **Заморожены legal hold (149-ФЗ ОРИ)**: «Чат и комментарии»,
  «Listening Party (v2)», «Chats / Track Share» — в TODO
  помечены `[FROZEN — legal hold]`; код жив, не реализуем
  новые пункты до оформления юрлица и подачи в реестр ОРИ.

- [~] **PWA Offline v2 — фундамент (2026-05-10)**: PrivateCore
  `offline_policy` + backend
  `GET /api/v1/tracks/{id}/offline-eligibility`, заголовок
  `X-Offline-Allowed` на HLS и progressive `/audio`. Workbox-плагин
  `cacheWillUpdate` отказывает в записи ответов с
  `X-Offline-Allowed: 0`. Frontend `offlineCache.downloadTrack`
  делает pre-flight к eligibility, применяет LRU и серверный
  лимит на размер. Раздел в `LEGAL.md` и
  `PRIVACY_POLICY.md §7.3`.

- [x] **Автоматический оффлайн-кеш по лайку (2026-05-10)**:
  `LikesContext.toggleLike` хукается на каждый лайк и вызывает
  `queueAutoCache(track)` из `frontend/src/lib/offlineCache.ts`
  (concurrency 1, eligibility-gate, fire-and-forget); снятие
  лайка вызывает `cancelAutoCache` + `removeTrack`. Добавлены
  `getCachedIdsSync`/`subscribeCacheChanges` для in-memory
  набора cachedIds (без сетевых запросов в рендере карточек).
  В `TrackCard` справа от лайка появляется зелёная иконка
  `check-circle` для треков с `access_mode='internal_stream'`.
  В `SettingsSheet` — toggle «Авто-сохранение лайкнутых
  треков», селект «Лимит оффлайн-кеша» (none/1/5/20 ГБ),
  статистика usage и кнопка «Очистить». Лимит общий — не
  server-cap, а либо пользовательский выбор, либо
  `navigator.storage.estimate() * 0.9`; LRU вытесняет по
  `cachedAt`. При первом успешном кеше в сессии — toast
  с opt-out. i18n `settings.offline*` + `offline.*` (ru/en).
  Уточнения в `LEGAL.md` § «Локальный оффлайн-кэш» и
  `PRIVACY_POLICY.md §7.3` про триггер «по лайку, выключаемо».

- [~] **Музыкальные профили и статистика (фундамент,
  2026-05-10)**: PrivateCore `user_top_policy` (window 7d/30d/
  90d/all, blend log(completed)+log(likes), thresholds);
  backend `ListenEventRepository.aggregate_user_top_tracks/
  genres`, `StatsService.get_user_top_tracks/genres`,
  `GET /api/v1/users/me/top`; frontend `api.getMyTop` готов
  к использованию (UI Home/Profile — следующая итерация).
  `PRIVACY_POLICY.md §7.4`.

- [~] **Anti-Abuse Fingerprinting (фундамент, 2026-05-10)**:
  PrivateCore `abuse_fingerprint_policy` (Decision PASS/
  THROTTLE/REQUIRE_CAPTCHA/LOCKOUT, opaque `AbuseSignals`,
  пороги, retention 30 дней, lockout 15 мин); backend
  миграция `0088_abuse_events`, `AbuseEvent` модель,
  `AbuseSignalMiddleware` (читает `X-DS-Signal`),
  `AbuseSignalService.evaluate_event` (decision + persist
  best-effort). Frontend `lib/clientSignals.ts` (opaque hash
  без биометрии и pixel-perfect canvas) + `ConsentBanner`
  + автодобавление `X-DS-Signal` в `api.request` только
  после согласия. `PRIVACY_POLICY.md §7.5`.

- [x] **Anti-abuse wiring + retention (2026-05-10)**:
  `AbuseEventRepository.recent_signal_counts` (1h / 10m
  windows), `app/services/abuse_guard.py` собирает sliding-
  window сигналы (включая Tor через `app/core/tor_checker`)
  и зовёт PrivateCore `evaluate`; подключён в
  `auth.py:/telegram` (LOCKOUT → 423, REQUIRE_CAPTCHA → 429).
  Daily cron `daily-abuse-events-pruner` (cron `15 4 * * *`)
  чистит rows старше `ABUSE_EVENT_RETENTION_SECONDS`
  (миграция `0089`).

- [x] **PWA «Сохранить оффлайн» в TrackCardSheet и
  «Ваш топ» на Home (2026-05-10)**: добавлен пункт
  `tcs-action-btn` (download/check icon, скрыт для
  `third_party_stream`); `MyTopView` `/my-top` с tabs
  7d/30d/90d/all отображает топ-жанры и топ-треки из
  `GET /users/me/top`; новая плитка `quickMyTop` в
  `MIX_SHORTCUT_TILES`, i18n RU/EN.

- [x] **Polish-pass (2026-05-10)**:
  - Admin `TracksRoute`: вкладка `Deleted` в
    `AdminRangeSwitch` (`adminApi.listDeletedTracks`); в
    строках этой вкладки — кнопки `Восстановить`
    (`adminApi.restoreTrack`) и `Удалить навсегда`
    (`adminApi.hardDeleteTrackForever` со step-up confirm).
  - `PlayerContext.playNext`: при `navigator.onLine === false`
    в начале вызывает `_fallbackToCachedTrack(track.id)`
    (offline-first); если кэш пуст или все треки уже
    проигрывались — падает обратно к обычным веткам
    manualQueue/radio/prefetch/adjacent. Если все ветки тоже
    не нашли next — повторно пробует кэш как последний шанс
    (через `import('@/lib/offlineCache').getCachedTracks` с
    фильтром `unavailableTrackIdsRef`).
  - `ListenerStats` показывает CTA «Открыть Ваш топ →»,
    ведущий на `/my-top`.
  - `app/api/v1/auth_email.py /verify` подключён к
    `evaluate_auth_event(kind="login")` (LOCKOUT → 423,
    REQUIRE_CAPTCHA → 429), как `auth.py /telegram`.
  - `app/models/__init__.py` импортирует `AbuseEvent`
    (включает таблицу в `Base.metadata.create_all` для
    in-memory pytest БД).
  - Listening-by-day: `aggregate_user_minutes_by_day`
    в `ListenEventRepository`, `StatsService.get_user_minutes_by_day`,
    `GET /api/v1/users/me/listening-by-day?days=N` (1-90);
    `api.getMyListeningByDay` + bar-chart в `MyTopView`
    (`my-top-hours__*` стили в `global.css`); i18n RU/EN
    `myTop.hoursByDay` / `myTop.hoursTotal`.
  - i18n `myTop.*`, `trash.*`, `consent.*` (RU/EN)
    в `i18n_extra_*.json`.
  - Тесты: `tests/app/repositories/test_abuse_event.py`
    (recent_signal_counts: empty / short-vs-long window /
    failed_login_burst по score, `prune_older_than`),
    `tests/app/services/test_abuse_signal_service.py`
    (PASS-event persists; LOCKOUT при «грязных» сигналах),
    3 новых сценария в `test_stats_service.py`
    (top tracks отбрасывает листенеров ниже порога,
    нормализация window, top genres).

- [x] **Onboarding v2 — заверение flow и переключение App.tsx (2026-05-08)**:
  собран главный компонент `OnboardingV2` (`Welcome → Profile → Genres →
  Swipe → Complete`), подключён в `App.tsx` вместо старого
  `Onboarding`, переведены `AvatarBuilder` / диалог аватара на i18n
  ключи `redesign.onboardingV2.profile.*`. Backend часть (`/onboarding/
  bootstrap`, `/profile-defaults`, `/profile`, `/taste-swipe` GET+POST)
  отформатирована Black + чистый Ruff. Тестовая батарея
  (`tests/app/services/test_onboarding_service.py`,
  `tests/app/api/v1/test_onboarding.py`) — 25 passed. Frontend
  `tsc --noEmit` + `npm run build` зелёные. Параллельно восстановлен
  синтаксис в `DotSoundPrivateCore/src/dotsound_private_core/services/
  lyrics_provider.py` (две слипшиеся в одну строку конструкции из ASR
  loop), без них тесты не загружались.

## Оптимизация импорта (2026-05-10)

- [x] **Параллельный prefetch SC-поиска + полный рефакторинг import-воркеров**:
  - `app/services/external_import_worker.py`: до главного цикла вызывается
    `_prefetch_sc_searches` — все SC-запросы для треков без локального
    совпадения запускаются параллельно (семафор `import_sc_prefetch_concurrency=3`),
    каждый слот спит джиттер перед вызовом API и пишет результат в Redis.
    Главный цикл попадает в кеш — сохраняет время ожидания поиска.
    Оба запроса (`artist+title` и только `title`) прогреваются заранее.
  - `app/utils/text_normalize.py`: `normalize_for_match` — зеркало SQL
    `lower(trim(...))` для консистентного preflight-матчинга.
  - `app/repositories/track.py`: `find_existing_by_normalized_title_artist`
    — пакетный запрос по (title, artist) без внешних вызовов.
  - `app/services/import_service.py`: Redis-флаги отмены вместо refresh DB
    в каждом item-цикле; `set_cancel_flag`, `is_cancel_flag_set`, `clear_cancel_flag`.
  - `app/services/import_queue_dispatcher.py`: `sweep_stuck_jobs` сбрасывает
    зависшие `importing` джобы в `queued`.
  - `app/services/external_providers.py`: `asyncio.wait_for` с `scan_timeout_seconds`
    для scan_playlist_url + код ошибки `scan_timeout`.
  - `app/services/soundcloud_service.py`: `_sc_http_client_cache` — persistent
    `httpx.AsyncClient` per (proxy, timeout); `close_sc_http_clients` при shutdown.
  - `app/services/import_worker.py` (Telegram): single httpx.AsyncClient на job,
    retry с backoff `_download_audio_with_retry`, `_BOT_RETRYABLE_STATUSES`.
  - `alembic/versions/0090_import_job_items.py`: таблица `import_job_items`
    (PK job_id+idx, status, track_id FK, title, artist, sc_url, reason, local_match,
    updated_at) с `ON CONFLICT DO NOTHING` для идемпотентного resume.
  - `app/models/import_job_item.py` + `app/repositories/import_job_item.py`:
    полный CRUD; `seed_pending`, `list_pending_indices`, `mark_done/failed/skipped/deduped`,
    `counters`, `list_for_response`.
  - `app/config.py`: новые knobs `import_job_stuck_after_seconds`,
    `import_cancel_flag_ttl_seconds`, `import_lease_check_every_n_items`,
    `import_sc_prefetch_concurrency`, `import_telegram_download_*`,
    `scan_timeout_seconds`.

- [x] **Radio disc audio-reactive visualizer (2026-05-10)**: `AudioRipple`
  компонент заменяет `BeatPulse` на RadioView — при воспроизведении
  считывает низкочастотную энергию из Web Audio `AnalyserNode` (bass bins
  0–690 Hz) и: (1) синхронно ведёт `--bp-phase` → CSS scale/bounce вместо
  BPM-сайна; (2) при превышении порога рождает canvas ripple-кольца,
  расширяющиеся от края диска наружу с fade 860 мс. Фолбэк на BPM-сайн
  при недоступном analyser. `canvas z-index: -1` внутри stacking context
  → кольца под обложкой, но видимы как halo. `tsc --noEmit` зелёный.

- [x] **Profile stats tab (2026-05-10)**: `ProfileStatsTab` (период 7/30/365д),
  hero-KPI (минуты/часы), CSS genre bars (ширина пропорционально maxGenreMin),
  top-artists list, `RecapShareCard` с реальными `totalMinutes` и `collageSrc`
  из top-tracks cover keys; кнопка «Статистика» (chart-bar) в `ProfileActions`;
  i18n RU/EN; `tsc --noEmit` зелёный.

- [x] **Radio + Stats — 5 visual improvements (2026-05-10)**:
  (1) Genre bars: `AnimatePresence key={period}` + staggered `m.li` + `m.div width`
  — Framer Motion управляет анимацией вместо CSS transition.
  (2) Canvas share poster: `lib/shareCard.ts` `createSharePoster` → коллаж 2×2 +
  big number + watermark на OffscreenCanvas → PNG download через `downloadBlob`.
  (3) AudioRipple adaptive beat: `Float32Array(120)` rolling avg; threshold =
  `max(0.12, avg×1.4)` — работает на тихих и громких треках; reset на деактив.
  (4) Sparkline в ProfileStatsTab: `HoursChart` + `getMyListeningByDay` в
  `Promise.all`; i18n `myTop.*` добавлены в ru.json + en.json.
  (5) Ring color from cover palette: RadioView → `extractCoverPalette(heroCover)`
  (кешируется AmbientStage) → `tones[0]` → `AudioRipple ringColor` →
  `hexToRgba` для stroke колец вместо белого.
