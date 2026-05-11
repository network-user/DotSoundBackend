/**
 * Auto-resume hook for chunked uploads stored in IndexedDB.
 *
 * Watches ``navigator.onLine`` transitions and the page lifecycle;
 * when connectivity returns and the queue has pending/paused jobs,
 * resumes them one at a time. Jobs that hit a quota lock are left
 * in ``blocked_quota`` so the UI can prompt the user.
 */

import { useEffect } from 'react'

import {
  cancelUpload,
  getUploadStatus,
  uploadFile,
} from '@/lib/chunkedUploader'
import {
  listJobs,
  removeJob,
  updateJob,
  type UploadJob,
} from '@/lib/uploadQueue'

let running = false

async function resumeJob(job: UploadJob): Promise<void> {
  if (!job.upload_id) {
    await updateJob(job.id, {
      status: 'failed',
      error: 'no upload_id',
    })
    return
  }
  try {
    const remote = await getUploadStatus(job.upload_id)
    if (remote.status !== 'active') {
      if (remote.status === 'completed') {
        await removeJob(job.id)
      } else {
        await updateJob(job.id, {
          status: 'failed',
          error: `session ${remote.status}`,
        })
      }
      return
    }
    await updateJob(job.id, { status: 'uploading', error: null })
    const completed = await uploadFile(
      {
        upload_id: job.upload_id,
        chunk_size: Math.floor(job.total_size / Math.max(1, remote.expected_chunks)),
        expected_chunks: remote.expected_chunks,
        expires_at: remote.expires_at,
        completed_chunks: remote.completed_chunks,
      },
      job.file_blob,
      {
        cover: job.cover_blob ?? null,
        onProgress: async (info) => {
          await updateJob(job.id, {
            completed_chunks: Array.from(
              new Set([
                ...(job.completed_chunks || []),
                ...Array.from({ length: info.completedChunks }, (_, i) => i),
              ]),
            ),
          })
        },
      },
    )
    await updateJob(job.id, {
      status: 'completed',
      upload_id: completed.upload_id,
    })
    await removeJob(job.id)
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : 'unknown error'
    const isQuota =
      /quota/i.test(msg) && /exceed/i.test(msg)
    await updateJob(job.id, {
      status: isQuota ? 'blocked_quota' : 'failed',
      error: msg,
    })
  }
}

async function drainQueue(): Promise<void> {
  if (running) return
  running = true
  try {
    const jobs = await listJobs()
    const resumable = jobs.filter(
      (j) =>
        j.status === 'pending' ||
        j.status === 'paused' ||
        j.status === 'failed',
    )
    for (const job of resumable) {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        break
      }
      await resumeJob(job)
    }
  } finally {
    running = false
  }
}

export function useUploadQueueAutoResume(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return
    const onOnline = () => {
      void drainQueue()
    }
    window.addEventListener('online', onOnline)
    if (navigator.onLine) {
      void drainQueue()
    }
    return () => {
      window.removeEventListener('online', onOnline)
    }
  }, [])
}

export async function cancelQueuedJob(jobId: string): Promise<void> {
  const job = (await listJobs()).find((j) => j.id === jobId)
  if (!job) return
  if (job.upload_id) {
    try {
      await cancelUpload(job.upload_id)
    } catch {
      /* network may be offline; we still mark locally */
    }
  }
  await updateJob(jobId, { status: 'cancelled' })
  await removeJob(jobId)
}
