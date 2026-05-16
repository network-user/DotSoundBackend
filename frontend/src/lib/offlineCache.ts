import { api } from '@/lib/api'
import type { Track } from '@/types/api'

const CACHE_NAME = 'offline-tracks-v1'
const DB_NAME = 'dotsound-offline'
const DB_VERSION = 2
const STORE = 'tracks'

const LS_AUTO_CACHE = 'setting-offline-auto-cache'
const LS_CACHE_LIMIT = 'setting-offline-cache-limit'
const LS_ONBOARDING = 'ds:auto-cache-toast-shown'
const LS_UNPINNED_TTL_DAYS = 'setting-offline-unpinned-ttl-days'

const DAY_MS = 24 * 60 * 60 * 1000
const HOUR_MS = 60 * 60 * 1000
const UNPINNED_TTL_DEFAULT_DAYS = 7
const RECOMMENDATION_TTL_HOURS = 48
const GC_FILL_THRESHOLD = 0.8
const GC_FILL_TARGET = 0.6
const PLAYBACK_WARM_MAX_BYTES = 64 * 1024 * 1024
const PLAYBACK_WARM_TOTAL_MAX_BYTES = 192 * 1024 * 1024
const PLAYBACK_WARM_MAX_ENTRIES = 8
const LS_PLAYBACK_WARM_INDEX = 'ds:playback-warm-index:v1'

type FetchPriority = 'low' | 'high' | 'auto'

interface FetchInitWithPriority extends RequestInit {
  priority?: FetchPriority
}

interface PlaybackWarmRecord {
  trackId: number
  url: string
  bytes: number
  warmedAt: number
}

export interface PlaybackWarmResult {
  ok: boolean
  bytes: number
  alreadyCached: boolean
}

export type CacheSource =
  | 'manual'
  | 'liked'
  | 'queue-prefetch'
  | 'recommendation'

const LEGACY_AUDIO = (id: number) =>
  `/api/v1/tracks/${id}/audio`

export function trackProgressiveAudioUrl(
  id: number,
): string {
  return `${LEGACY_AUDIO(id)}?force_progressive=true`
}

interface OfflineRecord {
  trackId: number
  track?: Track
  cachedAt: number
  bytes: number
  audioUrl: string
  source?: CacheSource
  pinned?: boolean
  lastPlayedAt?: number | null
}

function audioUrlForTrackId(trackId: number): string {
  return trackProgressiveAudioUrl(trackId)
}

async function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (event) => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, {
          keyPath: 'trackId',
        })
      }
      const oldVersion = event.oldVersion ?? 0
      if (oldVersion < 2) {
        const tx = req.transaction
        if (tx) {
          const store = tx.objectStore(STORE)
          const cursorReq = store.openCursor()
          cursorReq.onsuccess = () => {
            const cursor = cursorReq.result
            if (!cursor) return
            const rec = cursor.value as OfflineRecord
            if (rec.source == null) rec.source = 'manual'
            if (rec.pinned == null) rec.pinned = true
            if (rec.lastPlayedAt === undefined) {
              rec.lastPlayedAt = null
            }
            cursor.update(rec)
            cursor.continue()
          }
        }
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export function isOfflineCacheSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'caches' in window &&
    'indexedDB' in window
  )
}

export async function isCached(
  trackId: number,
): Promise<boolean> {
  if (!isOfflineCacheSupported()) return false
  try {
    const db = await openDb()
    return new Promise<boolean>((resolve) => {
      const tx = db.transaction(STORE, 'readonly')
      const store = tx.objectStore(STORE)
      const req = store.get(trackId)
      req.onsuccess = () => {
        resolve(Boolean(req.result))
        db.close()
      }
      req.onerror = () => {
        resolve(false)
        db.close()
      }
    })
  } catch {
    return false
  }
}

export async function getCachedAudioUrl(
  trackId: number,
): Promise<string | null> {
  if (!isOfflineCacheSupported()) return null
  try {
    const cache = await caches.open(CACHE_NAME)
    let res = await cache.match(
      trackProgressiveAudioUrl(trackId),
    )
    if (!res) {
      res = await cache.match(LEGACY_AUDIO(trackId))
    }
    if (!res) return null
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  } catch {
    return null
  }
}

function readPlaybackWarmIndex(): PlaybackWarmRecord[] {
  try {
    const raw = localStorage.getItem(LS_PLAYBACK_WARM_INDEX)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((item): PlaybackWarmRecord | null => {
        if (!item || typeof item !== 'object') return null
        const rec = item as Partial<PlaybackWarmRecord>
        if (
          typeof rec.trackId !== 'number' ||
          typeof rec.url !== 'string' ||
          typeof rec.bytes !== 'number' ||
          typeof rec.warmedAt !== 'number'
        ) {
          return null
        }
        return rec as PlaybackWarmRecord
      })
      .filter((rec): rec is PlaybackWarmRecord => rec !== null)
  } catch {
    return []
  }
}

function writePlaybackWarmIndex(records: PlaybackWarmRecord[]): void {
  try {
    localStorage.setItem(
      LS_PLAYBACK_WARM_INDEX,
      JSON.stringify(records),
    )
  } catch {
    /* ignore */
  }
}

function upsertPlaybackWarmRecord(
  record: PlaybackWarmRecord,
): PlaybackWarmRecord[] {
  const next = readPlaybackWarmIndex().filter(
    (item) =>
      item.trackId !== record.trackId && item.url !== record.url,
  )
  next.push(record)
  writePlaybackWarmIndex(next)
  return next
}

async function trimPlaybackWarmCache(
  cache: Cache,
  records = readPlaybackWarmIndex(),
): Promise<void> {
  const unique = new Map<string, PlaybackWarmRecord>()
  for (const rec of records) {
    unique.set(`${rec.trackId}:${rec.url}`, rec)
  }
  const warmOnly: PlaybackWarmRecord[] = []
  for (const rec of unique.values()) {
    if (await isCached(rec.trackId)) continue
    warmOnly.push(rec)
  }
  warmOnly.sort((a, b) => b.warmedAt - a.warmedAt)
  let total = warmOnly.reduce((sum, rec) => sum + rec.bytes, 0)
  const keep = [...warmOnly]
  while (
    keep.length > PLAYBACK_WARM_MAX_ENTRIES ||
    total > PLAYBACK_WARM_TOTAL_MAX_BYTES
  ) {
    const evicted = keep.pop()
    if (!evicted) break
    total -= evicted.bytes
    try {
      await cache.delete(evicted.url)
    } catch {
      /* ignore */
    }
  }
  writePlaybackWarmIndex(keep)
}

export async function warmProgressiveAudioForPlayback(
  trackId: number,
  options?: {
    signal?: AbortSignal
    maxBytes?: number
  },
): Promise<PlaybackWarmResult> {
  const failed: PlaybackWarmResult = {
    ok: false,
    bytes: 0,
    alreadyCached: false,
  }
  if (!isOfflineCacheSupported()) return failed
  const signal = options?.signal
  if (signal?.aborted) return failed
  const url = trackProgressiveAudioUrl(trackId)
  try {
    if (await isCached(trackId)) {
      return { ok: true, bytes: 0, alreadyCached: true }
    }
    const cache = await caches.open(CACHE_NAME)
    const existing = await cache.match(url)
    if (existing) {
      const bytes = Number(existing.headers.get('content-length') || 0)
      const records = upsertPlaybackWarmRecord({
        trackId,
        url,
        bytes,
        warmedAt: Date.now(),
      })
      await trimPlaybackWarmCache(cache, records)
      return { ok: true, bytes, alreadyCached: true }
    }
    const init: FetchInitWithPriority = {
      credentials: 'same-origin',
      cache: 'default',
      signal,
      priority: 'low',
    }
    const res = await fetch(url, init)
    if (!res.ok || res.status === 206) {
      try {
        await res.body?.cancel()
      } catch {
        /* ignore */
      }
      return failed
    }
    if (res.headers.get('X-Offline-Allowed') === '0') {
      try {
        await res.body?.cancel()
      } catch {
        /* ignore */
      }
      return failed
    }
    const maxBytes = options?.maxBytes ?? PLAYBACK_WARM_MAX_BYTES
    const len = Number(res.headers.get('content-length') || 0)
    if (!Number.isFinite(len) || len <= 0 || len > maxBytes) {
      try {
        await res.body?.cancel()
      } catch {
        /* ignore */
      }
      return failed
    }
    await cache.put(url, res.clone())
    try {
      await res.body?.cancel()
    } catch {
      /* ignore */
    }
    const records = upsertPlaybackWarmRecord({
      trackId,
      url,
      bytes: len,
      warmedAt: Date.now(),
    })
    await trimPlaybackWarmCache(cache, records)
    return { ok: true, bytes: len, alreadyCached: false }
  } catch {
    return failed
  }
}

export class OfflineNotAllowedError extends Error {
  reason: string
  constructor(reason: string) {
    super(`Offline not allowed: ${reason}`)
    this.reason = reason
  }
}

interface EligibilityLimits {
  maxTrackBytes: number
  maxTotalBytes: number
}

async function checkOfflineEligibility(
  trackId: number,
): Promise<EligibilityLimits> {
  const res = await api.getOfflineEligibility(trackId)
  if (!res.allowed) {
    throw new OfflineNotAllowedError(res.reason)
  }
  return {
    maxTrackBytes: res.max_track_bytes,
    maxTotalBytes: res.max_total_bytes_per_user,
  }
}

const CACHE_LIMIT_BYTES: Record<string, number> = {
  '1gb': 1 * 1024 * 1024 * 1024,
  '5gb': 5 * 1024 * 1024 * 1024,
  '20gb': 20 * 1024 * 1024 * 1024,
}

export type CacheLimitChoice =
  | 'none'
  | '1gb'
  | '5gb'
  | '20gb'

export function getCacheLimitChoice(): CacheLimitChoice {
  if (typeof localStorage === 'undefined') return 'none'
  const v = localStorage.getItem(LS_CACHE_LIMIT)
  if (
    v === '1gb' ||
    v === '5gb' ||
    v === '20gb' ||
    v === 'none'
  )
    return v
  return 'none'
}

export function setCacheLimitChoice(v: CacheLimitChoice): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(LS_CACHE_LIMIT, v)
}

async function resolveCacheCeiling(): Promise<number> {
  const choice = getCacheLimitChoice()
  if (choice !== 'none') return CACHE_LIMIT_BYTES[choice]
  try {
    if (
      typeof navigator !== 'undefined' &&
      'storage' in navigator &&
      navigator.storage &&
      'estimate' in navigator.storage
    ) {
      const est = await navigator.storage.estimate()
      if (est.quota && Number.isFinite(est.quota)) {
        return Math.floor(est.quota * 0.9)
      }
    }
  } catch {
    /* ignore */
  }
  return Number.POSITIVE_INFINITY
}

/** Effective ceiling for the local cache in bytes.
 *
 * Returns the user-selected limit when set, otherwise 90% of the
 * browser storage quota. ``Infinity`` means no usable ceiling
 * could be determined.
 */
export async function getEffectiveCacheLimit(): Promise<number> {
  return resolveCacheCeiling()
}

async function evictUntilUnder(maxBytes: number): Promise<void> {
  if (!Number.isFinite(maxBytes)) return
  const records = await getCachedTracks()
  let total = records.reduce((s, r) => s + r.bytes, 0)
  if (total <= maxBytes) return
  const sorted = [...records].sort((a, b) => {
    const ap = a.pinned === false ? 0 : 1
    const bp = b.pinned === false ? 0 : 1
    if (ap !== bp) return ap - bp
    const aLast = a.lastPlayedAt ?? a.cachedAt
    const bLast = b.lastPlayedAt ?? b.cachedAt
    return aLast - bLast
  })
  for (const rec of sorted) {
    if (total <= maxBytes) break
    await removeTrack(rec.trackId)
    total -= rec.bytes
  }
}

export type DownloadOptions = {
  onProgress?: (loaded: number, total: number) => void
  source?: CacheSource
  pinned?: boolean
  signal?: AbortSignal
}

export class DownloadAbortedError extends Error {
  constructor() {
    super('Download aborted')
    this.name = 'DownloadAbortedError'
  }
}

function defaultPinnedForSource(source: CacheSource): boolean {
  return source === 'manual' || source === 'liked'
}

export async function downloadTrack(
  trackOrId: Track | number,
  optsOrProgress?:
    | DownloadOptions
    | ((loaded: number, total: number) => void),
): Promise<void> {
  if (!isOfflineCacheSupported())
    throw new Error('Offline cache не поддерживается')
  const opts: DownloadOptions =
    typeof optsOrProgress === 'function'
      ? { onProgress: optsOrProgress }
      : (optsOrProgress ?? {})
  const source: CacheSource = opts.source ?? 'manual'
  const pinned = opts.pinned ?? defaultPinnedForSource(source)
  const trackId =
    typeof trackOrId === 'number' ? trackOrId : trackOrId.id
  const trackMeta =
    typeof trackOrId === 'number' ? undefined : trackOrId
  const signal = opts.signal
  const throwIfAborted = () => {
    if (signal?.aborted) throw new DownloadAbortedError()
  }
  throwIfAborted()
  const limits = await checkOfflineEligibility(trackId)
  throwIfAborted()
  const url = audioUrlForTrackId(trackId)
  const res = await fetch(url, {
    credentials: 'include',
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(
      `Не удалось загрузить (${res.status})`,
    )
  }
  if (res.headers.get('X-Offline-Allowed') === '0') {
    throw new OfflineNotAllowedError('server_blocked')
  }
  const total = Number(
    res.headers.get('content-length') || 0,
  )
  const reader = res.body.getReader()
  let parts: BlobPart[] | null = []
  let loaded = 0
  const cancelReader = () => {
    try {
      void reader.cancel()
    } catch {
      /* ignore */
    }
  }
  const onAbort = () => cancelReader()
  signal?.addEventListener('abort', onAbort)
  try {
    while (true) {
      if (signal?.aborted) throw new DownloadAbortedError()
      const { done, value } = await reader.read()
      if (done) break
      const buf = value.buffer.slice(
        value.byteOffset,
        value.byteOffset + value.byteLength,
      ) as ArrayBuffer
      parts.push(buf)
      loaded += value.byteLength
      opts.onProgress?.(loaded, total)
    }
  } catch (err) {
    parts = null
    cancelReader()
    throw err
  } finally {
    signal?.removeEventListener('abort', onAbort)
  }
  const blob = new Blob(parts, {
    type: res.headers.get('content-type') || 'audio/mpeg',
  })
  parts = null
  if (blob.size > limits.maxTrackBytes) {
    throw new OfflineNotAllowedError('track_too_large')
  }
  throwIfAborted()
  const ceiling = await resolveCacheCeiling()
  if (Number.isFinite(ceiling)) {
    await evictUntilUnder(Math.max(0, ceiling - blob.size))
  }
  const cache = await caches.open(CACHE_NAME)
  await cache.put(
    url,
    new Response(blob, {
      headers: {
        'Content-Type':
          res.headers.get('content-type') ||
          'audio/mpeg',
        'Content-Length': String(blob.size),
      },
    }),
  )
  // Past this point Cache API has the blob. If IDB write fails,
  // roll back the cache entry so isCached()/getCachedAudioUrl() stay
  // consistent.
  let dbInstance: IDBDatabase | null = null
  try {
    dbInstance = await openDb()
    const db = dbInstance
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const getReq = store.get(trackId)
      tx.onabort = () =>
        reject(tx.error ?? new Error('IDB transaction aborted'))
      tx.onerror = () =>
        reject(tx.error ?? new Error('IDB transaction error'))
      getReq.onsuccess = () => {
        const existing = getReq.result as OfflineRecord | undefined
        const nextPinned =
          existing?.pinned === true ? true : pinned
        const record: OfflineRecord = {
          trackId,
          track: trackMeta ?? existing?.track,
          cachedAt: Date.now(),
          bytes: blob.size,
          audioUrl: url,
          source:
            existing?.source === 'liked' || existing?.source === 'manual'
              ? existing.source
              : source,
          pinned: nextPinned,
          lastPlayedAt: existing?.lastPlayedAt ?? null,
        }
        const putReq = store.put(record)
        putReq.onsuccess = () => resolve()
        putReq.onerror = () =>
          reject(putReq.error ?? new Error('IDB put failed'))
      }
      getReq.onerror = () =>
        reject(getReq.error ?? new Error('IDB get failed'))
    })
  } catch (err) {
    try {
      await cache.delete(url)
    } catch {
      /* best effort rollback */
    }
    throw err
  } finally {
    try {
      dbInstance?.close()
    } catch {
      /* ignore */
    }
  }
  cachedIds.add(trackId)
  notifyCacheChange()
}

export async function removeTrack(
  trackId: number,
): Promise<void> {
  if (!isOfflineCacheSupported()) return
  try {
    const cache = await caches.open(CACHE_NAME)
    await cache.delete(LEGACY_AUDIO(trackId))
    await cache.delete(
      trackProgressiveAudioUrl(trackId),
    )
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.delete(trackId)
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
  if (cachedIds.delete(trackId)) {
    notifyCacheChange()
  }
}

export async function getCachedTracks(): Promise<
  OfflineRecord[]
> {
  if (!isOfflineCacheSupported()) return []
  try {
    const db = await openDb()
    return new Promise<OfflineRecord[]>((resolve) => {
      const tx = db.transaction(STORE, 'readonly')
      const store = tx.objectStore(STORE)
      const req = store.getAll()
      req.onsuccess = () => {
        const list = (req.result ||
          []) as OfflineRecord[]
        resolve(
          list.sort(
            (a, b) => b.cachedAt - a.cachedAt,
          ),
        )
        db.close()
      }
      req.onerror = () => {
        resolve([])
        db.close()
      }
    })
  } catch {
    return []
  }
}

export async function getStorageInfo(): Promise<{
  used: number
  quota: number
}> {
  try {
    if (
      'storage' in navigator &&
      'estimate' in navigator.storage
    ) {
      const est = await navigator.storage.estimate()
      return {
        used: est.usage || 0,
        quota: est.quota || 0,
      }
    }
  } catch {
    /* ignore */
  }
  return { used: 0, quota: 0 }
}

export async function clearAllOffline(): Promise<void> {
  if (!isOfflineCacheSupported()) return
  try {
    await caches.delete(CACHE_NAME)
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.clear()
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
  if (cachedIds.size > 0) {
    cachedIds.clear()
    notifyCacheChange()
  }
}

const cachedIds = new Set<number>()
const cacheChangeListeners = new Set<() => void>()
let cachedIdsLoaded = false
let cachedIdsLoading: Promise<void> | null = null

function notifyCacheChange(): void {
  for (const fn of cacheChangeListeners) fn()
}

export function subscribeCacheChanges(
  cb: () => void,
): () => void {
  cacheChangeListeners.add(cb)
  return () => {
    cacheChangeListeners.delete(cb)
  }
}

export function getCachedIdsSync(): Set<number> {
  return cachedIds
}

export function isCachedSync(trackId: number): boolean {
  return cachedIds.has(trackId)
}

export async function ensureCachedIdsLoaded(): Promise<void> {
  if (cachedIdsLoaded) return
  if (cachedIdsLoading) {
    await cachedIdsLoading
    return
  }
  cachedIdsLoading = (async () => {
    const records = await getCachedTracks()
    cachedIds.clear()
    for (const r of records) cachedIds.add(r.trackId)
    cachedIdsLoaded = true
    notifyCacheChange()
  })()
  await cachedIdsLoading
  cachedIdsLoading = null
}

export function getAutoCacheEnabled(): boolean {
  if (typeof localStorage === 'undefined') return true
  return localStorage.getItem(LS_AUTO_CACHE) !== 'false'
}

export function setAutoCacheEnabled(v: boolean): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(LS_AUTO_CACHE, String(v))
}

export function getAutoCacheOnboardingShown(): boolean {
  if (typeof localStorage === 'undefined') return true
  return localStorage.getItem(LS_ONBOARDING) === '1'
}

export function markAutoCacheOnboardingShown(): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(LS_ONBOARDING, '1')
}

interface AutoCacheRequest {
  trackId: number
  track?: Track
  source: CacheSource
  pinned: boolean
  onSuccess?: () => void
}

const autoCacheQueue: AutoCacheRequest[] = []
const autoCacheSeenInSession = new Set<number>()
let autoCacheRunning = false

async function runAutoCacheLoop(): Promise<void> {
  if (autoCacheRunning) return
  autoCacheRunning = true
  let didDownload = false
  try {
    while (autoCacheQueue.length > 0) {
      const next = autoCacheQueue.shift()
      if (!next) continue
      if (cachedIds.has(next.trackId)) {
        if (next.pinned) {
          void setPinned(next.trackId, true)
        }
        continue
      }
      try {
        await downloadTrack(next.track ?? next.trackId, {
          source: next.source,
          pinned: next.pinned,
        })
        didDownload = true
        next.onSuccess?.()
      } catch {
        /* swallow — eligibility denial or transient failure */
      }
    }
  } finally {
    autoCacheRunning = false
    if (didDownload) {
      void runCacheGC().catch(() => {})
    }
  }
}

export function queueAutoCache(
  trackOrId: Track | number,
  options?: {
    onFirstSuccess?: () => void
    source?: CacheSource
    pinned?: boolean
  },
): void {
  if (!isOfflineCacheSupported()) return
  if (!getAutoCacheEnabled()) return
  const trackId =
    typeof trackOrId === 'number' ? trackOrId : trackOrId.id
  const track =
    typeof trackOrId === 'number' ? undefined : trackOrId
  const source: CacheSource = options?.source ?? 'liked'
  const pinned =
    options?.pinned ?? defaultPinnedForSource(source)
  if (autoCacheSeenInSession.has(trackId)) {
    if (pinned && cachedIds.has(trackId)) {
      void setPinned(trackId, true)
    }
    return
  }
  autoCacheSeenInSession.add(trackId)
  if (cachedIds.has(trackId)) {
    if (pinned) {
      void setPinned(trackId, true)
    }
    return
  }
  autoCacheQueue.push({
    trackId,
    track,
    source,
    pinned,
    onSuccess: options?.onFirstSuccess,
  })
  void runAutoCacheLoop()
}

export function cancelAutoCache(trackId: number): void {
  autoCacheSeenInSession.delete(trackId)
  for (let i = autoCacheQueue.length - 1; i >= 0; i--) {
    if (autoCacheQueue[i].trackId === trackId) {
      autoCacheQueue.splice(i, 1)
    }
  }
}

export async function setPinned(
  trackId: number,
  pinned: boolean,
): Promise<void> {
  if (!isOfflineCacheSupported()) return
  if (!cachedIds.has(trackId)) return
  try {
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.get(trackId)
      req.onsuccess = () => {
        const rec = req.result as OfflineRecord | undefined
        if (!rec) {
          resolve()
          return
        }
        rec.pinned = pinned
        const putReq = store.put(rec)
        putReq.onsuccess = () => resolve()
        putReq.onerror = () => resolve()
      }
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
    notifyCacheChange()
  } catch {
    /* ignore */
  }
}

export async function markPlayed(trackId: number): Promise<void> {
  if (!isOfflineCacheSupported()) return
  if (!cachedIds.has(trackId)) return
  try {
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.get(trackId)
      req.onsuccess = () => {
        const rec = req.result as OfflineRecord | undefined
        if (!rec) {
          resolve()
          return
        }
        rec.lastPlayedAt = Date.now()
        const putReq = store.put(rec)
        putReq.onsuccess = () => resolve()
        putReq.onerror = () => resolve()
      }
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
}

export function getUnpinnedTtlDays(): number {
  if (typeof localStorage === 'undefined') {
    return UNPINNED_TTL_DEFAULT_DAYS
  }
  const raw = localStorage.getItem(LS_UNPINNED_TTL_DAYS)
  const parsed = raw ? Number.parseInt(raw, 10) : NaN
  if (
    !Number.isFinite(parsed) ||
    parsed < 1 ||
    parsed > 365
  ) {
    return UNPINNED_TTL_DEFAULT_DAYS
  }
  return parsed
}

export function setUnpinnedTtlDays(days: number): void {
  if (typeof localStorage === 'undefined') return
  if (!Number.isFinite(days) || days < 1 || days > 365) {
    localStorage.removeItem(LS_UNPINNED_TTL_DAYS)
    return
  }
  localStorage.setItem(
    LS_UNPINNED_TTL_DAYS,
    String(Math.floor(days)),
  )
}

export async function clearUnpinned(): Promise<number> {
  if (!isOfflineCacheSupported()) return 0
  const records = await getCachedTracks()
  let removed = 0
  for (const rec of records) {
    if (rec.pinned === false) {
      await removeTrack(rec.trackId)
      removed++
    }
  }
  return removed
}

let gcRunning = false

export async function runCacheGC(
  opts?: { force?: boolean },
): Promise<void> {
  if (!isOfflineCacheSupported()) return
  if (gcRunning && !opts?.force) return
  gcRunning = true
  try {
    const records = await getCachedTracks()
    const now = Date.now()
    const ttlMs = getUnpinnedTtlDays() * DAY_MS
    const recommendationTtlMs =
      RECOMMENDATION_TTL_HOURS * HOUR_MS
    for (const rec of records) {
      if (rec.pinned === true) continue
      const sincePlayed =
        rec.lastPlayedAt != null
          ? now - rec.lastPlayedAt
          : now - rec.cachedAt
      if (
        rec.source === 'recommendation' &&
        rec.lastPlayedAt == null &&
        now - rec.cachedAt > recommendationTtlMs
      ) {
        await removeTrack(rec.trackId)
        continue
      }
      if (sincePlayed > ttlMs) {
        await removeTrack(rec.trackId)
      }
    }
    const ceiling = await resolveCacheCeiling()
    if (Number.isFinite(ceiling) && ceiling > 0) {
      const remaining = await getCachedTracks()
      let total = remaining.reduce((s, r) => s + r.bytes, 0)
      const threshold = ceiling * GC_FILL_THRESHOLD
      if (total > threshold) {
        const target = ceiling * GC_FILL_TARGET
        const unpinnedFirst = [...remaining]
          .filter((r) => r.pinned !== true)
          .sort((a, b) => {
            const aLast = a.lastPlayedAt ?? a.cachedAt
            const bLast = b.lastPlayedAt ?? b.cachedAt
            return aLast - bLast
          })
        for (const rec of unpinnedFirst) {
          if (total <= target) break
          await removeTrack(rec.trackId)
          total -= rec.bytes
        }
      }
    }
  } finally {
    gcRunning = false
  }
}

export interface StorageBreakdown {
  total: number
  byPinned: { pinned: number; unpinned: number }
  bySource: Record<CacheSource, number>
  count: number
}

export async function getStorageBreakdown(): Promise<StorageBreakdown> {
  const result: StorageBreakdown = {
    total: 0,
    byPinned: { pinned: 0, unpinned: 0 },
    bySource: {
      manual: 0,
      liked: 0,
      'queue-prefetch': 0,
      recommendation: 0,
    },
    count: 0,
  }
  if (!isOfflineCacheSupported()) return result
  const records = await getCachedTracks()
  for (const r of records) {
    result.total += r.bytes
    result.count++
    if (r.pinned === true) {
      result.byPinned.pinned += r.bytes
    } else {
      result.byPinned.unpinned += r.bytes
    }
    const src: CacheSource = r.source ?? 'manual'
    result.bySource[src] = (result.bySource[src] ?? 0) + r.bytes
  }
  return result
}

let gcSchedulerStarted = false

function startGcScheduler(): void {
  if (gcSchedulerStarted) return
  if (typeof window === 'undefined') return
  if (!isOfflineCacheSupported()) return
  gcSchedulerStarted = true
  window.setTimeout(() => {
    void runCacheGC().catch(() => {})
  }, 5000)
  window.setInterval(
    () => {
      void runCacheGC().catch(() => {})
    },
    60 * 60 * 1000,
  )
}

startGcScheduler()

export interface BulkDownloadProgress {
  done: number
  total: number
  ok: number
  skipped: number
  failed: number
  currentTrackId: number | null
}

export interface BulkDownloadResult {
  ok: number
  skipped: number
  failed: number
  aborted: boolean
}

export interface BulkDownloadOptions {
  signal?: AbortSignal
  source?: CacheSource
  pinned?: boolean
  onProgress?: (state: BulkDownloadProgress) => void
}

/** Download every track in ``tracks`` into the offline cache.
 *
 * Runs sequentially so a single shared abort signal can stop the
 * batch cleanly and so we don't multiply network pressure. Tracks
 * already cached are counted as ``skipped`` and not re-downloaded.
 * Per-track failures (ineligible / network error) don't abort the
 * batch — they're tallied in ``failed``.
 */
export async function downloadTracksBulk(
  tracks: Track[],
  options: BulkDownloadOptions = {},
): Promise<BulkDownloadResult> {
  const signal = options.signal
  const source: CacheSource = options.source ?? 'manual'
  const pinned =
    options.pinned ?? defaultPinnedForSource(source)
  const total = tracks.length
  let ok = 0
  let skipped = 0
  let failed = 0
  let aborted = false

  const emit = (currentTrackId: number | null, done: number) => {
    options.onProgress?.({
      done,
      total,
      ok,
      skipped,
      failed,
      currentTrackId,
    })
  }

  emit(null, 0)

  for (let i = 0; i < tracks.length; i++) {
    if (signal?.aborted) {
      aborted = true
      break
    }
    const track = tracks[i]
    emit(track.id, i)
    if (isCachedSync(track.id)) {
      skipped += 1
      continue
    }
    try {
      await downloadTrack(track, {
        source,
        pinned,
        signal,
      })
      ok += 1
    } catch (err) {
      if (err instanceof DownloadAbortedError) {
        aborted = true
        break
      }
      failed += 1
    }
  }

  emit(null, ok + skipped + failed)
  return { ok, skipped, failed, aborted }
}

export type { OfflineRecord }
