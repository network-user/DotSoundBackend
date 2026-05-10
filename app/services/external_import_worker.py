import asyncio
import contextlib
import difflib
import hashlib
import json
import random
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.models.track import Track
from app.repositories.import_job_item import ImportJobItemRepository
from app.repositories.track import TrackRepository
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)
from app.services.import_service import (
    clear_cancel_flag,
    is_cancel_flag_set,
)
from app.services.soundcloud_service import (
    SoundCloudRateLimitError,
    SoundCloudService,
)
from app.utils.text_normalize import normalize_for_match

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DURATION_TOLERANCE = 0.20
_MIN_TITLE_SCORE = 0.55
_SEARCH_LIMIT = 10
_SC_SEARCH_CACHE_PREFIX = "sc:search"


def _sc_search_cache_key(query: str) -> str:
    return (
        f"{_SC_SEARCH_CACHE_PREFIX}:"
        f"{hashlib.sha256(query.encode()).hexdigest()}"
    )


async def _get_cached_sc_search(
    query: str,
) -> list[dict] | None:  # type: ignore[type-arg]
    try:
        raw = await get_redis_client().get(_sc_search_cache_key(query))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]
    except Exception:
        return None


async def _set_cached_sc_search(
    query: str,
    results: list[dict],  # type: ignore[type-arg]
) -> None:
    if not results:
        return
    with contextlib.suppress(Exception):
        await get_redis_client().set(
            _sc_search_cache_key(query),
            json.dumps(results),
            ex=settings.sc_search_cache_ttl_seconds,
        )


def _is_slow_mode(selected: list) -> bool:  # type: ignore[type-arg]
    return len(selected) > settings.import_slow_mode_threshold


def _jitter_delay(slow: bool) -> float:
    if slow:
        return random.uniform(
            settings.import_slow_mode_jitter_min_seconds,
            settings.import_slow_mode_jitter_max_seconds,
        )
    return random.uniform(
        settings.import_track_jitter_min_seconds,
        settings.import_track_jitter_max_seconds,
    )


async def _search_with_retry(
    sc_service: SoundCloudService,
    query: str,
    *,
    max_retries: int,
    base_delay: float,
    delay_multiplier: float,
    job_id: int,
) -> list[dict]:  # type: ignore[type-arg]
    """Search SC with exponential backoff on rate-limit errors."""
    for attempt in range(max_retries + 1):
        try:
            return await sc_service.search(query, limit=_SEARCH_LIMIT)
        except SoundCloudRateLimitError as exc:
            if attempt >= max_retries:
                raise
            wait = (
                exc.retry_after
                if exc.retry_after
                else base_delay * (2**attempt) * delay_multiplier
            )
            logger.warning(
                "external_import_rate_limited",
                job_id=job_id,
                query=query,
                attempt=attempt,
                wait_seconds=wait,
                http_status=exc.status_code,
            )
            await asyncio.sleep(wait)
    return []


def _lease_lost(job: ImportJob, expected_lease: str) -> bool:
    actual = (job.tracks_data or {}).get("worker_lease")
    return actual != expected_lease


async def _preflight_local_matches(
    track_repo: TrackRepository,
    selected: list,  # type: ignore[type-arg]
) -> dict[tuple[str, str], Track]:
    """Return ``(norm_title, norm_artist) -> Track`` for items already in DB.

    Only items that have BOTH title and artist are considered — a
    title-only match is too noisy to skip the external matcher
    safely. Items without a hit just pass through to the existing
    SoundCloud pipeline.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in selected:
        title = normalize_for_match(item.get("title"))
        artist = normalize_for_match(item.get("artist"))
        if not title or not artist:
            continue
        key = (title, artist)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    if not pairs:
        return {}
    return await track_repo.find_existing_by_normalized_title_artist(pairs)


def _lookup_local_match(
    matches: dict[tuple[str, str], Track],
    item: dict,  # type: ignore[type-arg]
) -> Track | None:
    if not matches:
        return None
    title = normalize_for_match(item.get("title"))
    artist = normalize_for_match(item.get("artist"))
    if not title or not artist:
        return None
    return matches.get((title, artist))


async def _prefetch_sc_searches(
    sc_service: SoundCloudService,
    items: list[dict],  # type: ignore[type-arg]
    *,
    job_id: int,
    slow: bool,
) -> None:
    """Warm the Redis SC-search cache for all pending items concurrently.

    Each slot acquires a semaphore, sleeps a random jitter, then fires
    one ``search`` call. Cache hits are skipped entirely. Errors are
    suppressed — a miss here just means the main loop does the live
    call. This separates the *search* latency from the serial main loop
    so both phases (search prefetch + ``import_or_get_track``) overlap
    in wall-clock time.

    Cancellation: a 1000-track prefetch can take 10–20 minutes. If the
    user cancels mid-prefetch we'd otherwise keep burning SC API calls
    until the queue drains. The shared ``cancelled`` flag short-circuits
    every remaining task as soon as any slot observes the Redis cancel
    flag.
    """
    concurrency = max(1, int(settings.import_sc_prefetch_concurrency))
    sem = asyncio.Semaphore(concurrency)
    cancelled = False
    stats = {"cache_hits": 0, "live_calls": 0, "errors": 0, "skipped": 0}

    async def _fetch_one(query: str) -> None:
        nonlocal cancelled
        if cancelled:
            stats["skipped"] += 1
            return
        cached = await _get_cached_sc_search(query)
        if cached is not None:
            stats["cache_hits"] += 1
            return
        async with sem:
            if cancelled:
                stats["skipped"] += 1
                return
            # One Redis check per real SC call. Cheap (a single
            # GET) and bounds the worst-case lag between cancel
            # and shutdown to roughly one slot's jitter+search.
            if await is_cancel_flag_set(job_id):
                cancelled = True
                stats["skipped"] += 1
                return
            await asyncio.sleep(_jitter_delay(slow))
            try:
                hits = await _search_with_retry(
                    sc_service,
                    query,
                    max_retries=settings.import_per_track_max_retries,
                    base_delay=settings.import_per_track_retry_base_delay_seconds,
                    delay_multiplier=1.0,
                    job_id=job_id,
                )
                await _set_cached_sc_search(query, hits)
                stats["live_calls"] += 1
            except Exception:
                stats["errors"] += 1
                logger.debug(
                    "external_import_prefetch_miss",
                    job_id=job_id,
                    query=query,
                )

    seen: set[str] = set()
    tasks: list[asyncio.Task[None]] = []
    for item in items:
        title = (item.get("title") or "").strip()
        artist = (item.get("artist") or "").strip()
        q = _build_query(title, artist)
        if q and q not in seen:
            seen.add(q)
            tasks.append(asyncio.create_task(_fetch_one(q)))
        # Pre-warm title-only query used by the fallback retry path.
        if title and artist and title not in seen:
            seen.add(title)
            tasks.append(asyncio.create_task(_fetch_one(title)))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(
        "external_import_prefetch_stats",
        job_id=job_id,
        total_queries=len(tasks),
        cache_hits=stats["cache_hits"],
        live_calls=stats["live_calls"],
        errors=stats["errors"],
        skipped=stats["skipped"],
        cancelled=cancelled,
    )


def _build_query(title: str, artist: str) -> str:
    parts = [p.strip() for p in (artist, title) if p and p.strip()]
    return " ".join(parts)


def _title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def _pick_best_sc_match(
    candidates: list[dict],
    target_title: str,
    target_duration_s: int | None,
) -> dict | None:
    """Return the best SoundCloud candidate, or None if nothing fits.

    Rules (per user spec):
      - Duration within ±20% of target when target is known
        (mandatory filter).
      - Title similarity ≥ ``_MIN_TITLE_SCORE`` (required).
      - Artist is intentionally NOT filtered — SoundCloud metadata
        is inconsistent, uploaders often rename artist.
    """
    best: dict | None = None
    best_score = -1.0
    for cand in candidates:
        duration_ms = cand.get("duration")
        if target_duration_s and duration_ms:
            duration_s = float(duration_ms) / 1000.0
            delta = abs(duration_s - target_duration_s) / (
                target_duration_s or 1
            )
            if delta > _DURATION_TOLERANCE:
                continue
        score = _title_similarity(target_title, cand.get("title") or "")
        if score > best_score:
            best_score = score
            best = cand
    if best is None or best_score < _MIN_TITLE_SCORE:
        return None
    return best


@broker.task
async def process_external_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if not job or job.status != "importing":
            logger.warning(
                "external_import_skip",
                job_id=job_id,
                reason="not_found_or_wrong_status",
            )
            return

        existing_data = job.tracks_data or {}
        selected_full = existing_data.get("selected", [])
        if not selected_full:
            job.status = "done"
            job.total_tracks = 0
            await session.commit()
            await session.refresh(job)
            from app.services.import_job_notifications import (
                send_import_job_finished_notification,
            )

            await send_import_job_finished_notification(session, job)
            return

        # Per-track state lives in ``import_job_items``. Seed the
        # rows once (idempotent on resume) and use the set of still
        # ``pending`` indices as the cursor — strictly more reliable
        # than the completed+failed counter, which assumed contiguous
        # progress and could double-process items in edge cases.
        items_repo = ImportJobItemRepository(session)
        await items_repo.seed_pending(job.id, selected_full)
        await session.commit()

        original_idx_list = await items_repo.list_pending_indices(job.id)
        selected = [selected_full[i] for i in original_idx_list]
        cursor_count = len(selected_full) - len(selected)

        # Worker lease: any zombie worker that wakes up after
        # ``sweep_stuck_jobs`` reset this row will see a different
        # lease on its next refresh and exit instead of fighting
        # the new worker for the same job.
        worker_lease = uuid.uuid4().hex
        job.tracks_data = {**existing_data, "worker_lease": worker_lease}
        await session.commit()
        await session.refresh(job)

        sc_service = SoundCloudService(settings.sc_client_id, session)
        library_repo = UserTrackLibraryRepository(session)
        track_repo = TrackRepository(session)

        if cursor_count > 0:
            logger.info(
                "external_import_resume",
                job_id=job_id,
                cursor=cursor_count,
                remaining=len(selected),
            )

        local_matches = await _preflight_local_matches(track_repo, selected)
        if local_matches:
            logger.info(
                "external_import_preflight_hits",
                job_id=job_id,
                hits=len(local_matches),
                total=len(selected),
            )

        slow = _is_slow_mode(selected)

        # Items that have no local match need a SoundCloud search.
        # Prefetch those searches in parallel so the main loop
        # hits the Redis cache instead of waiting on each network
        # round-trip serially.
        sc_items = [
            item
            for item in selected
            if _lookup_local_match(local_matches, item) is None
        ]
        if sc_items:
            logger.info(
                "external_import_prefetch_start",
                job_id=job_id,
                sc_items=len(sc_items),
                concurrency=settings.import_sc_prefetch_concurrency,
            )
            await _prefetch_sc_searches(
                sc_service,
                sc_items,
                job_id=job_id,
                slow=slow,
            )
        consecutive_failures = 0
        delay_multiplier = 1.0
        sc_call_index = 0
        items_seen = 0
        lease_check_every = max(
            1, int(settings.import_lease_check_every_n_items)
        )

        for pos, item in enumerate(selected):
            original_idx = original_idx_list[pos]
            if await is_cancel_flag_set(job_id):
                await session.refresh(job)
                job.status = "cancelled"
                await session.commit()
                break
            if items_seen % lease_check_every == 0:
                await session.refresh(job)
                if _lease_lost(job, worker_lease):
                    logger.warning(
                        "external_import_lease_lost",
                        job_id=job_id,
                    )
                    return
            items_seen += 1

            local_match = _lookup_local_match(local_matches, item)
            if local_match is not None:
                try:
                    await library_repo.add(
                        user_id=job.user_id,
                        track_id=local_match.id,
                        source=job.source,
                    )
                    job.completed_tracks += 1
                    await items_repo.mark_done(
                        job.id,
                        original_idx,
                        track_id=local_match.id,
                        title=local_match.title,
                        artist=local_match.artist,
                        sc_url=local_match.sc_url,
                        local_match=True,
                    )
                    await session.commit()
                    logger.info(
                        "external_import_local_match",
                        job_id=job_id,
                        track_id=local_match.id,
                        source=job.source,
                    )
                except Exception as exc:
                    await session.rollback()
                    await session.refresh(job)
                    job.failed_tracks += 1
                    await items_repo.mark_failed(
                        job.id,
                        original_idx,
                        title=local_match.title,
                        artist=local_match.artist,
                        reason=f"local_match_link_failed: {exc}",
                    )
                    await session.commit()
                    logger.warning(
                        "external_import_local_match_link_failed",
                        job_id=job_id,
                        track_id=local_match.id,
                        error=str(exc),
                    )
                continue

            # Jitter delay between SC calls to avoid rapid-fire API calls.
            # Counted on real SC calls only — local-match items don't
            # touch the network, so they shouldn't burn the budget.
            if sc_call_index > 0:
                await asyncio.sleep(_jitter_delay(slow) * delay_multiplier)
            sc_call_index += 1

            title = (item.get("title") or "").strip()
            artist = (item.get("artist") or "").strip()
            target_duration = item.get("duration_seconds")
            query = _build_query(title, artist)

            if not query:
                job.failed_tracks += 1
                await items_repo.mark_failed(
                    job.id,
                    original_idx,
                    title=title or "Unknown",
                    artist=artist or None,
                    reason="no_query",
                )
                await session.commit()
                continue

            try:
                results = await _get_cached_sc_search(query)
                if results is None:
                    results = await _search_with_retry(
                        sc_service,
                        query,
                        max_retries=settings.import_per_track_max_retries,
                        base_delay=settings.import_per_track_retry_base_delay_seconds,
                        delay_multiplier=delay_multiplier,
                        job_id=job_id,
                    )
                    await _set_cached_sc_search(query, results)
            except SoundCloudRateLimitError as exc:
                logger.warning(
                    "external_import_search_rate_limit_exhausted",
                    job_id=job_id,
                    query=query,
                    http_status=exc.status_code,
                )
                await session.refresh(job)
                job.failed_tracks += 1
                await items_repo.mark_failed(
                    job.id,
                    original_idx,
                    title=title,
                    artist=artist or None,
                    reason="rate_limited",
                )
                await session.commit()
                consecutive_failures += 1
                _fw = settings.import_adaptive_failure_window
                if consecutive_failures % _fw == 0:
                    delay_multiplier = min(
                        delay_multiplier * 2.0,
                        settings.import_adaptive_delay_multiplier_max,
                    )
                    logger.warning(
                        "external_import_adaptive_throttle",
                        job_id=job_id,
                        consecutive_failures=consecutive_failures,
                        new_multiplier=delay_multiplier,
                    )
                continue
            except Exception as exc:
                logger.error(
                    "external_import_search_failed",
                    job_id=job_id,
                    query=query,
                    error=str(exc),
                )
                await session.refresh(job)
                job.failed_tracks += 1
                await items_repo.mark_failed(
                    job.id,
                    original_idx,
                    title=title,
                    artist=artist or None,
                    reason="search_error",
                )
                await session.commit()
                continue

            best_match = _pick_best_sc_match(
                results,
                target_title=title,
                target_duration_s=(
                    int(target_duration)
                    if isinstance(target_duration, int | float)
                    else None
                ),
            )
            # Title-only retry when the first (artist+title) query
            # returned candidates but none fit. SoundCloud uploads
            # often have artist baked into the title, making the
            # combined query miss.
            if best_match is None and artist and results:
                try:
                    results_title_only = await _get_cached_sc_search(title)
                    if results_title_only is None:
                        results_title_only = await _search_with_retry(
                            sc_service,
                            title,
                            max_retries=settings.import_per_track_max_retries,
                            base_delay=settings.import_per_track_retry_base_delay_seconds,
                            delay_multiplier=delay_multiplier,
                            job_id=job_id,
                        )
                        await _set_cached_sc_search(title, results_title_only)
                    best_match = _pick_best_sc_match(
                        results_title_only,
                        target_title=title,
                        target_duration_s=(
                            int(target_duration)
                            if isinstance(target_duration, int | float)
                            else None
                        ),
                    )
                except Exception:
                    logger.debug(
                        "external_import_title_retry_failed",
                        job_id=job_id,
                    )

            if best_match is None:
                job.failed_tracks += 1
                await items_repo.mark_failed(
                    job.id,
                    original_idx,
                    title=title,
                    artist=artist or None,
                    reason="no_soundcloud_match",
                )
                await session.commit()
                consecutive_failures += 1
                _fw = settings.import_adaptive_failure_window
                if consecutive_failures % _fw == 0:
                    delay_multiplier = min(
                        delay_multiplier * 2.0,
                        settings.import_adaptive_delay_multiplier_max,
                    )
                    logger.warning(
                        "external_import_adaptive_throttle",
                        job_id=job_id,
                        consecutive_failures=consecutive_failures,
                        new_multiplier=delay_multiplier,
                    )
                continue

            try:
                try:
                    track = await sc_service.import_or_get_track(
                        sc_data=best_match,
                        uploader_id=job.user_id,
                        is_public=True,
                        skip_background_lyrics=True,
                    )
                except IntegrityError as exc:
                    await session.rollback()
                    logger.warning(
                        "external_import_dedup_race",
                        job_id=job_id,
                        error=str(exc),
                    )
                    fallback_url = best_match.get("permalink_url")
                    if not fallback_url:
                        raise
                    fallback_result = await session.execute(
                        select(Track).where(Track.sc_url == fallback_url)
                    )
                    fallback_track = fallback_result.scalar_one_or_none()
                    if fallback_track is None:
                        raise
                    track = fallback_track
                try:
                    await library_repo.add(
                        user_id=job.user_id,
                        track_id=track.id,
                        source=job.source,
                    )
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    logger.warning(
                        "external_import_library_add_failed",
                        job_id=job_id,
                        track_id=track.id,
                        error=str(exc),
                    )

                await session.refresh(job)
                job.completed_tracks += 1
                await items_repo.mark_done(
                    job.id,
                    original_idx,
                    track_id=track.id,
                    title=track.title,
                    artist=track.artist,
                    sc_url=track.sc_url,
                    local_match=False,
                )
                await session.commit()
                from app.services.search_index_notify import (
                    schedule_reindex_track,
                )

                await schedule_reindex_track(track.id)
                if track.artist:
                    from app.services.artist_service import ArtistService

                    artist_svc = ArtistService(session)
                    try:
                        await artist_svc.resolve_and_link(
                            track_id=track.id,
                            raw_artist_string=track.artist,
                            source=track.source_platform or "soundcloud",
                        )
                        await session.commit()
                    except Exception:
                        logger.warning(
                            "external_import_artist_link_failed",
                            track_id=track.id,
                        )
                        await session.rollback()
                logger.info(
                    "external_import_track_done",
                    job_id=job_id,
                    track_id=track.id,
                    source=job.source,
                )
                consecutive_failures = 0
                delay_multiplier = max(1.0, delay_multiplier / 2.0)
            except Exception as exc:
                logger.error(
                    "external_import_track_failed",
                    job_id=job_id,
                    query=query,
                    error=str(exc),
                )
                await session.refresh(job)
                job.failed_tracks += 1
                await items_repo.mark_failed(
                    job.id,
                    original_idx,
                    title=title,
                    artist=artist or None,
                    reason=f"import_error: {exc}",
                )
                await session.commit()
                consecutive_failures += 1
                _fw = settings.import_adaptive_failure_window
                if consecutive_failures % _fw == 0:
                    delay_multiplier = min(
                        delay_multiplier * 2.0,
                        settings.import_adaptive_delay_multiplier_max,
                    )

        await session.refresh(job)
        if _lease_lost(job, worker_lease):
            logger.warning(
                "external_import_lease_lost_at_finalize",
                job_id=job_id,
            )
            return
        if job.status != "cancelled":
            job.status = "done"

        imported, not_matched = await items_repo.list_for_response(job.id)
        job.tracks_data = {
            **(job.tracks_data or {}),
            "imported": imported,
            "not_matched": not_matched,
        }
        await session.commit()
        await session.refresh(job)
        await clear_cancel_flag(job_id)

        from app.services.import_job_notifications import (
            send_import_job_finished_notification,
        )

        await send_import_job_finished_notification(session, job)

        logger.info(
            "external_import_finished",
            job_id=job_id,
            source=job.source,
            completed=job.completed_tracks,
            failed=job.failed_tracks,
        )

        if imported and job.status == "done":
            # Local import keeps the module-load graph simple and
            # prevents a theoretical circular import on backend
            # startup. Fire-and-forget: the lyrics orchestrator
            # reads the job row itself and paces per-track work.
            from app.services.import_lyrics_worker import (
                process_import_lyrics_task,
            )

            try:
                await process_import_lyrics_task.kiq(job_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "import_lyrics_enqueue_failed",
                    job_id=job_id,
                    error=str(exc),
                )
