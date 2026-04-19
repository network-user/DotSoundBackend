import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { adminApi } from '../lib/adminApi'
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

function buildJobColumns(
  onOpen: (id: string) => void,
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
    header: 'Track',
    accessorKey: 'track_id',
  },
  {
    header: 'Status',
    cell: (i) => (
      <StatusPill
        kind={jobKind(i.row.original.status)}
      >
        {i.row.original.status}
      </StatusPill>
    ),
  },
  {
    header: 'Profile',
    accessorKey: 'profile',
  },
  {
    header: 'Worker',
    accessorKey: 'routed_to_worker',
  },
  {
    header: 'Attempts',
    accessorKey: 'attempts',
  },
  {
    header: 'Duration',
    cell: (i) =>
      i.row.original.duration_ms
        ? `${(
            i.row.original.duration_ms / 1000
          ).toFixed(1)}s`
        : '–',
  },
  ]
}

export function TasksRoute() {
  const { t } = useTranslation()
  const [activeJobId, setActiveJobId] = useState<
    string | null
  >(null)
  const queues = useQuery({
    queryKey: ['admin', 'tasks', 'queues'],
    queryFn: () => adminApi.listQueues(),
    refetchInterval: 15_000,
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
  const jobColumns = buildJobColumns((id) =>
    setActiveJobId(id),
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
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.tasks.lyricsJobs')}</h2>
        <DataTable
          columns={jobColumns}
          rows={
            (jobs.data?.items as
              | JobRow[]
              | undefined) || []
          }
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
