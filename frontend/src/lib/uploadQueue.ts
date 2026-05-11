/**
 * IndexedDB-backed queue for chunked uploads. Persists the file blob,
 * the upload plan, and per-chunk progress so we can resume after a
 * reload or after coming back online.
 *
 * Schema (db ``dotsound-uploads`` v1):
 *   - object store ``jobs`` keyed by ``id`` (string)
 *
 * The store is intentionally separate from ``dotsound-offline`` so
 * the existing offline cache code stays untouched.
 */

const DB_NAME = 'dotsound-uploads'
const DB_VERSION = 1
const STORE = 'jobs'

export type UploadJobStatus =
  | 'pending'
  | 'uploading'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'blocked_quota'

export interface UploadJob {
  id: string
  upload_id: string | null
  filename: string
  mime: string
  total_size: number
  audio_hash: string | null
  file_blob: Blob
  cover_blob: Blob | null
  completed_chunks: number[]
  meta: {
    title: string
    artist: string | null
    use_profile_artist: boolean
    genre: string | null
    is_public: boolean
  }
  status: UploadJobStatus
  error: string | null
  created_at: number
  updated_at: number
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => Promise<T> | T,
): Promise<T> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const s = t.objectStore(STORE)
    let result: T
    Promise.resolve(fn(s))
      .then((r) => {
        result = r
      })
      .catch((err) => reject(err))
    t.oncomplete = () => {
      db.close()
      resolve(result)
    }
    t.onabort = () => {
      db.close()
      reject(t.error)
    }
    t.onerror = () => {
      db.close()
      reject(t.error)
    }
  })
}

function genId(): string {
  return (
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).slice(2, 10)
  )
}

export async function enqueueJob(
  payload: Omit<UploadJob, 'id' | 'status' | 'error' | 'created_at' | 'updated_at'> & {
    status?: UploadJobStatus
  },
): Promise<UploadJob> {
  const now = Date.now()
  const job: UploadJob = {
    id: genId(),
    status: payload.status ?? 'pending',
    error: null,
    created_at: now,
    updated_at: now,
    ...payload,
  }
  await tx('readwrite', (store) => {
    store.put(job)
  })
  return job
}

export async function getJob(id: string): Promise<UploadJob | null> {
  return tx('readonly', (store) => {
    return new Promise<UploadJob | null>((resolve, reject) => {
      const r = store.get(id)
      r.onsuccess = () => resolve((r.result as UploadJob) || null)
      r.onerror = () => reject(r.error)
    })
  })
}

export async function listJobs(): Promise<UploadJob[]> {
  return tx('readonly', (store) => {
    return new Promise<UploadJob[]>((resolve, reject) => {
      const r = store.getAll()
      r.onsuccess = () => resolve((r.result as UploadJob[]) || [])
      r.onerror = () => reject(r.error)
    })
  })
}

export async function updateJob(
  id: string,
  patch: Partial<UploadJob>,
): Promise<UploadJob | null> {
  return tx('readwrite', async (store) => {
    return new Promise<UploadJob | null>((resolve, reject) => {
      const r = store.get(id)
      r.onsuccess = () => {
        const current = r.result as UploadJob | undefined
        if (!current) {
          resolve(null)
          return
        }
        const next = {
          ...current,
          ...patch,
          updated_at: Date.now(),
        }
        const put = store.put(next)
        put.onsuccess = () => resolve(next)
        put.onerror = () => reject(put.error)
      }
      r.onerror = () => reject(r.error)
    })
  })
}

export async function removeJob(id: string): Promise<void> {
  await tx('readwrite', (store) => {
    store.delete(id)
  })
}

export async function pendingCount(): Promise<number> {
  const jobs = await listJobs()
  return jobs.filter(
    (j) =>
      j.status === 'pending' ||
      j.status === 'paused' ||
      j.status === 'uploading' ||
      j.status === 'failed',
  ).length
}
