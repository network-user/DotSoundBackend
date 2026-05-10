import { api } from '@/lib/api'
import type { Track } from '@/types/api'

const CACHE_NAME = 'offline-tracks-v1'
const DB_NAME = 'dotsound-offline'
const DB_VERSION = 1
const STORE = 'tracks'

const LS_AUTO_CACHE = 'setting-offline-auto-cache'
const LS_CACHE_LIMIT = 'setting-offline-cache-limit'
const LS_ONBOARDING = 'ds:auto-cache-toast-shown'

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
}

function audioUrlForTrackId(trackId: number): string {
  return trackProgressiveAudioUrl(trackId)
}

async function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, {
          keyPath: 'trackId',
        })
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
  const res = (await api.getOfflineEligibility(trackId)) as {
    allowed: boolean
    reason: string
    max_track_bytes: number
    max_total_bytes_per_user: number
  }
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

async function evictUntilUnder(maxBytes: number): Promise<void> {
  if (!Number.isFinite(maxBytes)) return
  const records = await getCachedTracks()
  let total = records.reduce((s, r) => s + r.bytes, 0)
  if (total <= maxBytes) return
  const oldestFirst = [...records].sort(
    (a, b) => a.cachedAt - b.cachedAt,
  )
  for (const rec of oldestFirst) {
    if (total <= maxBytes) break
    await removeTrack(rec.trackId)
    total -= rec.bytes
  }
}

export async function downloadTrack(
  trackOrId: Track | number,
  onProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  if (!isOfflineCacheSupported())
    throw new Error('Offline cache не поддерживается')
  const trackId =
    typeof trackOrId === 'number' ? trackOrId : trackOrId.id
  const trackMeta =
    typeof trackOrId === 'number' ? undefined : trackOrId
  const limits = await checkOfflineEligibility(trackId)
  const url = audioUrlForTrackId(trackId)
  const res = await fetch(url, {
    credentials: 'include',
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
  const parts: BlobPart[] = []
  let loaded = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const buf = value.buffer.slice(
      value.byteOffset,
      value.byteOffset + value.byteLength,
    ) as ArrayBuffer
    parts.push(buf)
    loaded += value.byteLength
    onProgress?.(loaded, total)
  }
  const blob = new Blob(parts, {
    type: res.headers.get('content-type') || 'audio/mpeg',
  })
  if (blob.size > limits.maxTrackBytes) {
    throw new OfflineNotAllowedError('track_too_large')
  }
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
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const store = tx.objectStore(STORE)
    const record: OfflineRecord = {
      trackId,
      track: trackMeta,
      cachedAt: Date.now(),
      bytes: blob.size,
      audioUrl: url,
    }
    const req = store.put(record)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
    tx.oncomplete = () => db.close()
  })
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
  onSuccess?: () => void
}

const autoCacheQueue: AutoCacheRequest[] = []
const autoCacheSeenInSession = new Set<number>()
let autoCacheRunning = false

async function runAutoCacheLoop(): Promise<void> {
  if (autoCacheRunning) return
  autoCacheRunning = true
  try {
    while (autoCacheQueue.length > 0) {
      const next = autoCacheQueue.shift()
      if (!next) continue
      if (cachedIds.has(next.trackId)) continue
      try {
        await downloadTrack(next.track ?? next.trackId)
        next.onSuccess?.()
      } catch {
        /* swallow — eligibility denial or transient failure */
      }
    }
  } finally {
    autoCacheRunning = false
  }
}

export function queueAutoCache(
  trackOrId: Track | number,
  options?: { onFirstSuccess?: () => void },
): void {
  if (!isOfflineCacheSupported()) return
  if (!getAutoCacheEnabled()) return
  const trackId =
    typeof trackOrId === 'number' ? trackOrId : trackOrId.id
  const track =
    typeof trackOrId === 'number' ? undefined : trackOrId
  if (autoCacheSeenInSession.has(trackId)) return
  autoCacheSeenInSession.add(trackId)
  if (cachedIds.has(trackId)) return
  autoCacheQueue.push({
    trackId,
    track,
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

export type { OfflineRecord }
