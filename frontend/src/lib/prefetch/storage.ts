/**
 * Lightweight LRU registry of which tracks we have already warmed
 * (HLS manifest pulled, optionally first segments cached). Persists
 * in IndexedDB so a fresh session can re-use warm-data inserted by
 * the previous run.
 */

const DB_NAME = 'dotsound-prefetch'
const DB_VERSION = 1
const STORE = 'warm-index'

export interface WarmRecord {
  trackId: number
  warmedAt: number
  context: string
  bytes: number
  sourcePlatform: string | null
}

let _dbPromise: Promise<IDBDatabase | null> | null = null

function _isSupported(): boolean {
  return (
    typeof window !== 'undefined' && 'indexedDB' in window
  )
}

async function _openDb(): Promise<IDBDatabase | null> {
  if (!_isSupported()) return null
  if (_dbPromise) return _dbPromise
  _dbPromise = new Promise<IDBDatabase | null>((resolve) => {
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
    req.onerror = () => resolve(null)
  })
  return _dbPromise
}

export async function getStorageQuota(): Promise<{
  quota: number | null
  usage: number | null
}> {
  try {
    if (
      'storage' in navigator &&
      typeof navigator.storage.estimate === 'function'
    ) {
      const est = await navigator.storage.estimate()
      return {
        quota: est.quota ?? null,
        usage: est.usage ?? null,
      }
    }
  } catch {
    /* ignore */
  }
  return { quota: null, usage: null }
}

export async function persistWarmRecord(
  record: WarmRecord,
): Promise<void> {
  return persistWarmRecords([record])
}

export async function persistWarmRecords(
  records: WarmRecord[],
): Promise<void> {
  if (records.length === 0) return
  const db = await _openDb()
  if (!db) return
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      let pending = records.length
      const done = () => {
        pending -= 1
        if (pending === 0) resolve()
      }
      for (const record of records) {
        const req = store.put(record)
        req.onsuccess = done
        req.onerror = done
      }
      tx.onerror = () => resolve()
    } catch {
      resolve()
    }
  })
}

export async function listWarmRecords(): Promise<WarmRecord[]> {
  const db = await _openDb()
  if (!db) return []
  return new Promise<WarmRecord[]>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readonly')
      const store = tx.objectStore(STORE)
      const req = store.getAll()
      req.onsuccess = () =>
        resolve(((req.result as WarmRecord[]) || []))
      req.onerror = () => resolve([])
    } catch {
      resolve([])
    }
  })
}

export async function dropWarmRecord(
  trackId: number,
): Promise<void> {
  const db = await _openDb()
  if (!db) return
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.delete(trackId)
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
    } catch {
      resolve()
    }
  })
}

export async function clearWarmIndex(): Promise<void> {
  const db = await _openDb()
  if (!db) return
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.clear()
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
    } catch {
      resolve()
    }
  })
}
