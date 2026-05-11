/**
 * Resumable, cancellable chunked uploader for the v2 upload API.
 *
 * Public surface:
 *   - initUpload(meta) -> opens the server-side session
 *   - uploadFile(plan, file, opts) -> drives chunks to completion
 *   - cancelUpload(uploadId) -> aborts on the server
 *   - getUploadStatus(uploadId) -> snapshot for resume
 *
 * Behaviour:
 *   - 2 chunks in flight at once (mobile-friendly)
 *   - exponential backoff retry per chunk (500/1000/2000/4000ms)
 *   - 4xx responses fail fast; only network / 5xx are retried
 *   - AbortController support so the caller can cancel cleanly
 */

export interface UploadInitMeta {
  filename: string
  mime: string
  total_size: number
  audio_hash: string | null
  title: string
  artist: string | null
  use_profile_artist: boolean
  genre: string | null
  is_public: boolean
  upload_terms_accepted: boolean
}

export interface UploadPlan {
  upload_id: string
  chunk_size: number
  expected_chunks: number
  expires_at: string
  completed_chunks: number[]
}

export interface UploadStatus {
  upload_id: string
  status: 'active' | 'completed' | 'cancelled' | 'expired'
  completed_chunks: number[]
  expected_chunks: number
  expires_at: string
  track_id: number | null
}

export interface UploadCompleted {
  track_id: number
  upload_id: string
}

export interface UploadOptions {
  signal?: AbortSignal
  onProgress?: (info: {
    completedBytes: number
    totalBytes: number
    completedChunks: number
    expectedChunks: number
  }) => void
  cover?: Blob | null
  maxParallel?: number
  maxRetries?: number
}

const DEFAULT_PARALLEL = 2
const DEFAULT_RETRIES = 4

function authHeaders(): HeadersInit {
  const token =
    typeof window !== 'undefined'
      ? window.localStorage.getItem('dotsound:token')
      : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function _sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('aborted', 'AbortError'))
      return
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export async function initUpload(
  meta: UploadInitMeta,
): Promise<UploadPlan> {
  const res = await fetch('/api/v1/tracks/upload/init', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(meta),
  })
  if (!res.ok) {
    throw new Error(await _readError(res, 'upload init failed'))
  }
  return (await res.json()) as UploadPlan
}

export async function getUploadStatus(
  uploadId: string,
): Promise<UploadStatus> {
  const res = await fetch(`/api/v1/tracks/upload/${uploadId}`, {
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(await _readError(res, 'status fetch failed'))
  }
  return (await res.json()) as UploadStatus
}

export async function cancelUpload(uploadId: string): Promise<void> {
  await fetch(`/api/v1/tracks/upload/${uploadId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
}

async function uploadChunk(
  uploadId: string,
  index: number,
  blob: Blob,
  signal: AbortSignal | undefined,
  maxRetries: number,
): Promise<void> {
  let attempt = 0
  while (true) {
    attempt += 1
    try {
      const form = new FormData()
      form.append('chunk', blob, `chunk_${index}`)
      const res = await fetch(
        `/api/v1/tracks/upload/${uploadId}/chunk/${index}`,
        {
          method: 'PUT',
          headers: authHeaders(),
          body: form,
          signal,
        },
      )
      if (res.ok) return
      if (res.status >= 400 && res.status < 500) {
        throw new Error(
          await _readError(res, `chunk ${index} rejected`),
        )
      }
      throw new Error(
        await _readError(res, `chunk ${index} failed (${res.status})`),
      )
    } catch (err) {
      if (signal?.aborted) throw err
      if (attempt > maxRetries) throw err
      const backoff = Math.min(4000, 500 * 2 ** (attempt - 1))
      await _sleep(backoff, signal)
    }
  }
}

export async function uploadFile(
  plan: UploadPlan,
  file: Blob,
  opts: UploadOptions = {},
): Promise<UploadCompleted> {
  const {
    signal,
    onProgress,
    cover,
    maxParallel = DEFAULT_PARALLEL,
    maxRetries = DEFAULT_RETRIES,
  } = opts

  const total = file.size
  const completedSet = new Set(plan.completed_chunks)
  let chunksDone = completedSet.size

  const remaining: number[] = []
  for (let i = 0; i < plan.expected_chunks; i++) {
    if (!completedSet.has(i)) remaining.push(i)
  }

  let pointer = 0
  const workers: Promise<void>[] = []
  for (let w = 0; w < Math.max(1, maxParallel); w++) {
    workers.push(
      (async () => {
        while (true) {
          if (signal?.aborted) {
            throw new DOMException('aborted', 'AbortError')
          }
          const myIdx = pointer
          if (myIdx >= remaining.length) return
          pointer += 1
          const chunkIndex = remaining[myIdx]
          const start = chunkIndex * plan.chunk_size
          const end = Math.min(start + plan.chunk_size, total)
          const slice = file.slice(start, end)
          await uploadChunk(
            plan.upload_id,
            chunkIndex,
            slice,
            signal,
            maxRetries,
          )
          completedSet.add(chunkIndex)
          chunksDone += 1
          if (onProgress) {
            onProgress({
              completedBytes: Math.min(
                total,
                chunksDone * plan.chunk_size,
              ),
              totalBytes: total,
              completedChunks: chunksDone,
              expectedChunks: plan.expected_chunks,
            })
          }
        }
      })(),
    )
  }
  await Promise.all(workers)

  const completeForm = new FormData()
  if (cover) {
    completeForm.append('cover', cover, 'cover')
  }
  const completeRes = await fetch(
    `/api/v1/tracks/upload/${plan.upload_id}/complete`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: completeForm,
      signal,
    },
  )
  if (!completeRes.ok) {
    throw new Error(
      await _readError(completeRes, 'upload finalize failed'),
    )
  }
  return (await completeRes.json()) as UploadCompleted
}

export async function checkDuplicate(
  audioHash: string,
  sizeBytes: number,
): Promise<{
  exists: boolean
  track_id?: number
  title?: string
  uploaded_at?: string
}> {
  const res = await fetch('/api/v1/tracks/check-duplicate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({
      audio_hash: audioHash,
      size_bytes: sizeBytes,
    }),
  })
  if (!res.ok) {
    throw new Error(
      await _readError(res, 'duplicate check failed'),
    )
  }
  return res.json()
}

async function _readError(res: Response, fallback: string): Promise<string> {
  try {
    const j = await res.json()
    return (j?.detail as string) || fallback
  } catch {
    return fallback
  }
}
