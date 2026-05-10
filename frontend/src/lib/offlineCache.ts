import { api } from '@/lib/api'
import type { Track } from '@/types/api'

const CACHE_NAME = 'offline-tracks-v1'
const DB_NAME = 'dotsound-offline'
const DB_VERSION = 1
const STORE = 'tracks'

const LEGACY_AUDIO = (id: number) =>
  `/api/v1/tracks/${id}/audio`

export function trackProgressiveAudioUrl(
  id: number,
): string {
  return `${LEGACY_AUDIO(id)}?force_progressive=true`
}

interface OfflineRecord {
  trackId: number
  track: Track
  cachedAt: number
  bytes: number
  audioUrl: string
}

function audioUrlForTrack(track: Track): string {
  return trackProgressiveAudioUrl(track.id)
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

function isSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'caches' in window &&
    'indexedDB' in window
  )
}

export async function isCached(
  trackId: number,
): Promise<boolean> {
  if (!isSupported()) return false
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
  if (!isSupported()) return null
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

async function checkOfflineEligibility(
  trackId: number,
): Promise<{ maxTrackBytes: number; maxTotalBytes: number }> {
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

async function evictUntilUnder(maxBytes: number): Promise<void> {
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
  track: Track,
  onProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  if (!isSupported())
    throw new Error('Offline cache не поддерживается')
  const limits = await checkOfflineEligibility(track.id)
  const url = audioUrlForTrack(track)
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
  await evictUntilUnder(
    Math.max(0, limits.maxTotalBytes - blob.size),
  )
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
      trackId: track.id,
      track,
      cachedAt: Date.now(),
      bytes: blob.size,
      audioUrl: url,
    }
    const req = store.put(record)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
    tx.oncomplete = () => db.close()
  })
}

export async function removeTrack(
  trackId: number,
): Promise<void> {
  if (!isSupported()) return
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
}

export async function getCachedTracks(): Promise<
  OfflineRecord[]
> {
  if (!isSupported()) return []
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
  if (!isSupported()) return
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
}

export type { OfflineRecord }
