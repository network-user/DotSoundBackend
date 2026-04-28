import { useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { LyricsJobDetail } from '../components/widgets/LyricsJobDetail'
import { StatusPill } from '../components/widgets/StatusPill'

interface QueueRow {
  name: string
  length: number | null
}

interface JobRow {
  id: string
  track_id: number
  status: string
  profile: string
  routed_to_worker: string | null
  attempts: number
  duration_ms: number | null
  created_at: string
  error: string | null
  requested_by_user_id?: number | null
}

interface ComputeJobRow {
  id: string
  job_type: string
  job_label: string
  target_kind: string | null
  target_id: string | null
  status: string
  attempts: number
  last_error: string | null
  claimed_by: string | null
  created_at: string
}

const queueColumns: ColumnDef<QueueRow>[] = [
  {
    header: 'Queue',
    accessorKey: 'name',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<string>()}
      </span>
    ),
  },
  { header: 'Length', accessorKey: 'length' },
]

function jobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done') return 'ok'
  if (status === 'error') return 'error'
  if (status === 'queued' || status === 'running')
    return 'warn'
  return 'unknown'
}

function computeJobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'succeeded') return 'ok'
  if (status === 'failed') return 'error'
  if (status === 'pending' || status === 'claimed')
    return 'warn'
  return 'unknown'
}

function computeTypeUi(jobType: string): {
  icon: string
  pillKind: StatusKind
  cssMod: string
} {
  switch (jobType) {
    case 'track_audio_features':
      return {
        icon: 'eq',
        pillKind: 'warn',
        cssMod: 'audio',
      }
    case 'catalog_ingest_normalize':
      return {
        icon: 'list',
        pillKind: 'unknown',
        cssMod: 'catalog',
      }
    case 'artist_features_update':
      return {
        icon: 'user',
        pillKind: 'ok',
        cssMod: 'artist',
      }
    case 'artist_similarity_index':
      return {
        icon: 'share',
        pillKind: 'ok',
        cssMod: 'sim-artist',
      }
    case 'track_similarity_index':
      return {
        icon: 'link',
        pillKind: 'warn',
        cssMod: 'sim-track',
      }
    default:
      return {
        icon: 'queue',
        pillKind: 'unknown',
        cssMod: 'other',
      }
  }
}

function computeTypeTexts(
  jobType: string,
  t: TFunction,
): { slug: string; hint: string } {
  const slugKey = `admin.tasks.computeTypes.${jobType}.slug`
  const hintKey = `admin.tasks.computeTypes.${jobType}.hint`
  const slugTry = t(slugKey)
  const hintTry = t(hintKey)
  return {
    slug:
      slugTry === slugKey
        ? t('admin.tasks.computeTypes._fallback.slug')
        : slugTry,
    hint:
      hintTry === hintKey
        ? t('admin.tasks.computeTypes._fallback.hint')
        : hintTry,
  }
}

function buildComputeColumns(
  t: TFunction,
): ColumnDef<ComputeJobRow>[] {
  return [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <span
          className="admin-mono"
          title={i.getValue<string>()}
        >
          {String(i.getValue<string>()).slice(0, 10)}
        </span>
      ),
    },
    {
      header: t('admin.tasks.jobKind'),
      id: 'compute_job_kind',
      accessorFn: (row) => row.job_label,
      cell: (i) => {
        const row = i.row.original
        const ui = computeTypeUi(row.job_type)
        const texts = computeTypeTexts(row.job_type, t)
        return (
          <div
            className={`admin-compute-type admin-compute-type--${ui.cssMod}`}
            title={`${texts.hint}\n${row.job_type}`}
          >
            <Icon
              name={ui.icon}
              size={18}
              className="admin-compute-type__icon"
              aria-hidden
            />
            <div className="admin-compute-type__main">
              <StatusPill kind={ui.pillKind}>
                {texts.slug}
              </StatusPill>
              <div className="admin-compute-type__title">
                {row.job_label}
              </div>
            </div>
          </div>
        )
      },
    },
    {
      header: t('admin.tasks.computeTarget'),
      id: 'target',
      accessorFn: (row) =>
        `${row.target_kind || '–'} ${row.target_id || ''}`,
    },
    {
      header: t('admin.tasks.detail.status'),
      accessorKey: 'status',
      cell: (i) => (
        <StatusPill
          kind={computeJobKind(
            i.row.original.status,
          )}
        >
          {i.row.original.status}
        </StatusPill>
      ),
    },
    {
      header: t('admin.tasks.detail.attempts'),
      accessorKey: 'attempts',
    },
  ]
}

function buildJobColumns(
  t: TFunction,
  onOpen: (id: string) => void,
  onCancel: (id: string) => void,
  cancelLabel: string,
): ColumnDef<JobRow>[] {
  return [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => {
      const id = i.getValue<string>()
      return (
        <button
          type="button"
          className="admin-link admin-mono"
          onClick={() => onOpen(id)}
          title={id}
        >
          {String(id).slice(0, 8)}
        </button>
      )
    },
  },
  {
    header: t('admin.tasks.detail.track'),
    accessorKey: 'track_id',
  },
  {
    header: t('admin.tasks.detail.status'),
    accessorKey: 'status',
    cell: (i) => (
      <StatusPill
        kind={jobKind(i.row.original.status)}
      >
        {i.row.original.status}
      </StatusPill>
    ),
  },
  {
    header: t('admin.tasks.detail.profile'),
    accessorKey: 'profile',
  },
  {
    header: t('admin.tasks.requestedByColumn'),
    id: 'requested_by',
    accessorKey: 'requested_by_user_id',
    cell: (i) => {
      const uid = i.row.original.requested_by_user_id
      if (uid == null) {
        return t('admin.tasks.requestedByAuto')
      }
      return String(uid)
    },
  },
  {
    header: t('admin.tasks.detail.worker'),
    accessorKey: 'routed_to_worker',
  },
  {
    header: t('admin.tasks.detail.attempts'),
    accessorKey: 'attempts',
  },
  {
    header: t('admin.tasks.detail.duration'),
    accessorKey: 'duration_ms',
    cell: (i) =>
      i.row.original.duration_ms
        ? `${(
            i.row.original.duration_ms / 1000
          ).toFixed(1)}s`
        : '–',
  },
  {
    id: 'actions',
    header: '',
    enableSorting: false,
    cell: (i) => {
      const { id, status } = i.row.original
      const cancellable =
        status === 'queued' || status === 'running'
      if (!cancellable) return null
      return (
        <button
          type="button"
          className="admin-link"
          onClick={(e) => {
            e.stopPropagation()
            onCancel(id)
          }}
        >
          {cancelLabel}
        </button>
      )
    },
  },
  ]
}

export function TasksRoute() {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const qc = useQueryClient()
  const [activeJobId, setActiveJobId] = useState<
    string | null
  >(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const queues = useQuery({
    queryKey: ['admin', 'tasks', 'queues'],
    queryFn: () => adminApi.listQueues(),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const computeJobs = useQuery({
    queryKey: ['admin', 'tasks', 'compute-jobs'],
    queryFn: () =>
      adminApi.listComputeJobs({
        page: 1,
        size: 50,
      }),
    refetchInterval: activeJobId ? false : 15_000,
    refetchIntervalInBackground: false,
  })
  const jobs = useQuery({
    queryKey: ['admin', 'tasks', 'lyrics-jobs'],
    queryFn: () =>
      adminApi.listLyricsJobs({
        page: 1,
        size: 50,
      }),
    refetchInterval: activeJobId ? false : 15_000,
    refetchIntervalInBackground: false,
  })
  const computeRows =
    (computeJobs.data?.items as ComputeJobRow[] | undefined) ||
    []
  const rows = ((jobs.data?.items as JobRow[] | undefined) || [])
  const queuedCount = rows.filter(
    (r) => r.status === 'queued',
  ).length

  const handleCancelOne = async (id: string) => {
    try {
      await adminApi.cancelLyricsJob(id)
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'lyrics-jobs'],
      })
    } catch {}
  }

  const handleCancelAll = async () => {
    if (bulkBusy) return
    const ok = await showConfirm(
      t('admin.tasks.cancelAllConfirm', {
        count: queuedCount,
      }),
      { danger: true },
    )
    if (!ok) return
    setBulkBusy(true)
    try {
      await adminApi.cancelAllQueuedLyricsJobs()
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'lyrics-jobs'],
      })
    } catch {}
    finally {
      setBulkBusy(false)
    }
  }

  const computeColumns = buildComputeColumns(t)
  const jobColumns = buildJobColumns(
    t,
    (id) => setActiveJobId(id),
    handleCancelOne,
    t('admin.tasks.cancelRow'),
  )

  return (
    <div>
      <h1>{t('admin.tasks.title')}</h1>
      <section className="admin-card">
        <h2>{t('admin.tasks.queues')}</h2>
        <DataTable
          columns={queueColumns}
          rows={
            (queues.data?.items as QueueRow[]) ||
            []
          }
          enableSorting
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.tasks.computeJobs')}</h2>
        <p className="admin-card__sub">
          {t('admin.tasks.computeJobsHint')}
        </p>
        <DataTable
          columns={computeColumns}
          rows={computeRows}
          enableSorting
        />
      </section>
      <section className="admin-card">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.lyricsJobs')}
          </h2>
          {queuedCount > 0 && (
            <Press
              variant="primary"
              onClick={handleCancelAll}
              disabled={bulkBusy}
            >
              {t('admin.tasks.cancelQueueButton', {
                count: queuedCount,
              })}
            </Press>
          )}
        </div>
        <DataTable
          columns={jobColumns}
          rows={rows}
          enableSorting
        />
        <p className="admin-card__sub">
          {t('admin.tasks.detail.openHint')}
        </p>
      </section>
      {activeJobId && (
        <LyricsJobDetail
          jobId={activeJobId}
          onClose={() => setActiveJobId(null)}
        />
      )}
    </div>
  )
}
