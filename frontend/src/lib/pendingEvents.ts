// Lightweight offline-event queue.
//
// When the network is down (or a fetch fails), we stash the
// payload in IndexedDB and replay it once the browser comes
// back online. Used for play counts and listen signals so we
// don't drop analytics during commutes / spotty connections.

const DB_NAME = 'dotsound-pending'
const DB_VERSION = 1
const STORE = 'events'

type PendingKind =
  | 'post-play'
  | 'record-listen'
  | 'client-telemetry'
  | 'mutation'

interface PendingEvent {
  id?: number
  kind: PendingKind
  url: string
  body: string
  method?: string
  createdAt: number
  attempts: number
}

interface DispatchOptions {
  silent?: boolean
}

function isSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'indexedDB' in window
  )
}

async function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, {
          keyPath: 'id',
          autoIncrement: true,
        })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function addPending(
  ev: PendingEvent,
): Promise<void> {
  if (!isSupported()) return
  try {
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.add(ev)
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
}

async function listPending(): Promise<PendingEvent[]> {
  if (!isSupported()) return []
  try {
    const db = await openDb()
    return new Promise<PendingEvent[]>((resolve) => {
      const tx = db.transaction(STORE, 'readonly')
      const store = tx.objectStore(STORE)
      const req = store.getAll()
      req.onsuccess = () => {
        resolve(
          (req.result || []) as PendingEvent[],
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

async function deletePending(
  id: number,
): Promise<void> {
  if (!isSupported()) return
  try {
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.delete(id)
      req.onsuccess = () => resolve()
      req.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
}

async function bumpAttempts(
  id: number,
): Promise<void> {
  if (!isSupported()) return
  try {
    const db = await openDb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const getReq = store.get(id)
      getReq.onsuccess = () => {
        const ev = getReq.result as
          | PendingEvent
          | undefined
        if (!ev) {
          resolve()
          return
        }
        ev.attempts += 1
        store.put(ev)
        resolve()
      }
      getReq.onerror = () => resolve()
      tx.oncomplete = () => db.close()
    })
  } catch {
    /* ignore */
  }
}

async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    // Lazily import api.ts to avoid a static cycle (api.ts may
    // schedule a flush via this module during retry handling).
    const { api } = await import('@/lib/api')
    const t = api.getToken()
    return t ? { Authorization: `Bearer ${t}` } : {}
  } catch {
    return {}
  }
}

async function attemptSend(
  ev: PendingEvent,
): Promise<boolean> {
  try {
    const init: RequestInit = {
      method: ev.method || 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(await getAuthHeader()),
      },
    }
    if (ev.body && ev.body.length > 0) {
      init.body = ev.body
    }
    const res = await fetch(ev.url, init)
    return res.ok
  } catch {
    return false
  }
}

let flushing = false
let flushScheduled = false

export async function flushPending(): Promise<void> {
  if (flushing) {
    flushScheduled = true
    return
  }
  flushing = true
  try {
    const items = await listPending()
    for (const ev of items) {
      if (!ev.id) continue
      if (ev.attempts >= 5) {
        await deletePending(ev.id)
        continue
      }
      const ok = await attemptSend(ev)
      if (ok) await deletePending(ev.id)
      else await bumpAttempts(ev.id)
    }
  } finally {
    flushing = false
    if (flushScheduled) {
      flushScheduled = false
      void flushPending()
    }
  }
}

export async function queueOrSend(
  kind: PendingKind,
  url: string,
  payload: unknown,
  opts: DispatchOptions = {},
): Promise<void> {
  const body = JSON.stringify(payload)
  const online =
    typeof navigator === 'undefined'
      ? true
      : navigator.onLine
  const ev: PendingEvent = {
    kind,
    url,
    body,
    createdAt: Date.now(),
    attempts: 0,
  }
  if (online) {
    const ok = await attemptSend(ev)
    if (ok) return
  }
  await addPending(ev)
  if (!opts.silent && online) {
    void flushPending()
  }
}

/**
 * Queue an arbitrary user-mutation (like/dislike/follow/comment) so it
 * gets replayed when the device returns online. Use ONLY for actions
 * where the optimistic UI has already updated and the server response
 * is non-essential for the next interaction.
 */
export async function queueMutation(
  method: 'POST' | 'DELETE' | 'PUT' | 'PATCH',
  url: string,
  payload?: unknown,
): Promise<void> {
  const body = payload === undefined ? '' : JSON.stringify(payload)
  const ev: PendingEvent = {
    kind: 'mutation',
    url,
    body,
    method,
    createdAt: Date.now(),
    attempts: 0,
  }
  await addPending(ev)
  const online =
    typeof navigator === 'undefined'
      ? true
      : navigator.onLine
  if (online) void flushPending()
}

export function installOnlineFlush(): () => void {
  if (typeof window === 'undefined') return () => {}
  const handler = () => {
    void flushPending()
  }
  window.addEventListener('online', handler)
  if (navigator.onLine) handler()
  return () =>
    window.removeEventListener('online', handler)
}
