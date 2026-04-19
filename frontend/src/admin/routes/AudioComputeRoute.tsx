import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminFetch } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface WorkerRow {
  id: string
  name: string
  profile: string
  active: boolean
  suspended_reason: string | null
  last_seen_at: string | null
  last_ip: string | null
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
}

interface AuditRow {
  id: number
  worker_id: string | null
  ip: string | null
  action: string
  job_id: string | null
  status_code: number | null
  created_at: string
}

const ROUTING_MODES = [
  'auto',
  'force_local_cpu',
  'force_remote_gpu',
  'disabled',
]

function jobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done') return 'ok'
  if (status === 'error') return 'error'
  if (
    status === 'queued' ||
    status === 'running'
  )
    return 'warn'
  return 'unknown'
}

const workerColumns: ColumnDef<WorkerRow>[] = [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<string>().slice(0, 12)}
      </span>
    ),
  },
  { header: 'Name', accessorKey: 'name' },
  { header: 'Profile', accessorKey: 'profile' },
  {
    header: 'Status',
    cell: (i) =>
      i.row.original.active ? (
        <StatusPill kind="ok">active</StatusPill>
      ) : (
        <StatusPill kind="error">
          {i.row.original.suspended_reason ||
            'inactive'}
        </StatusPill>
      ),
  },
  {
    header: 'Last seen',
    cell: (i) =>
      i.row.original.last_seen_at
        ? new Date(
            i.row.original.last_seen_at,
          ).toLocaleString()
        : '–',
  },
  {
    header: 'IP',
    accessorKey: 'last_ip',
  },
]

const jobColumns: ColumnDef<JobRow>[] = [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => (
      <span className="admin-mono">
        {String(i.getValue<string>()).slice(0, 8)}
      </span>
    ),
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
  { header: 'Profile', accessorKey: 'profile' },
  {
    header: 'Worker',
    accessorKey: 'routed_to_worker',
  },
  { header: 'Attempts', accessorKey: 'attempts' },
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

const auditColumns: ColumnDef<AuditRow>[] = [
  {
    header: 'When',
    cell: (i) =>
      new Date(
        i.row.original.created_at,
      ).toLocaleString(),
  },
  {
    header: 'Worker',
    accessorKey: 'worker_id',
    cell: (i) => (
      <span className="admin-mono">
        {(i.getValue<string | null>() || '')
          .toString()
          .slice(0, 8) || '–'}
      </span>
    ),
  },
  { header: 'Action', accessorKey: 'action' },
  {
    header: 'Job',
    accessorKey: 'job_id',
    cell: (i) => (
      <span className="admin-mono">
        {(i.getValue<string | null>() || '')
          .toString()
          .slice(0, 8) || '–'}
      </span>
    ),
  },
  {
    header: 'Status',
    accessorKey: 'status_code',
  },
  { header: 'IP', accessorKey: 'ip' },
]

export function AudioComputeRoute() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const workers = useQuery({
    queryKey: ['admin', 'compute', 'workers'],
    queryFn: () =>
      adminFetch<WorkerRow[]>(
        '/audio-compute/workers',
      ),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const jobs = useQuery({
    queryKey: ['admin', 'compute', 'jobs'],
    queryFn: () =>
      adminFetch<JobRow[]>(
        '/audio-compute/jobs',
      ),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const audit = useQuery({
    queryKey: ['admin', 'compute', 'audit'],
    queryFn: () =>
      adminFetch<AuditRow[]>(
        '/audio-compute/audit',
      ),
  })
  const routing = useQuery({
    queryKey: ['admin', 'compute', 'routing'],
    queryFn: () =>
      adminFetch<{ mode: string }>(
        '/audio-compute/routing',
      ),
  })
  const [newName, setNewName] = useState('')
  const [newProfile, setNewProfile] =
    useState('cpu_light')
  const [showSecret, setShowSecret] = useState<
    string | null
  >(null)

  const createWorker = useMutation({
    mutationFn: (payload: {
      name: string
      profile: string
    }) =>
      adminFetch<{
        id: string
        secret: string
      }>('/audio-compute/workers', {
        method: 'POST',
        body: payload,
      }),
    onSuccess: (data) => {
      setShowSecret(data.secret)
      setNewName('')
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
    },
  })

  const setMode = useMutation({
    mutationFn: (mode: string) =>
      adminFetch<{ mode: string }>(
        '/audio-compute/routing',
        {
          method: 'PATCH',
          body: { mode },
        },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: [
          'admin',
          'compute',
          'routing',
        ],
      })
    },
  })

  const revokeWorker = useMutation({
    mutationFn: (id: string) =>
      adminFetch(
        `/audio-compute/workers/${id}/revoke`,
        { method: 'POST', body: {} },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
    },
  })

  const rotateSecret = useMutation({
    mutationFn: (id: string) =>
      adminFetch<{ secret: string }>(
        `/audio-compute/workers/${id}/rotate_secret`,
        { method: 'POST', body: {} },
      ),
    onSuccess: (data) => {
      setShowSecret(data.secret)
    },
  })

  return (
    <div>
      <h1>{t('admin.audioCompute.title')}</h1>

      <section className="admin-card">
        <h2>{t('admin.audioCompute.routingMode')}</h2>
        <div className="admin-toolbar">
          <select
            value={
              routing.data?.mode || 'auto'
            }
            onChange={(e) =>
              setMode.mutate(e.target.value)
            }
          >
            {ROUTING_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <span className="admin-card__sub">
            current:{' '}
            <code>
              {routing.data?.mode || '…'}
            </code>
          </span>
        </div>
      </section>

      <section className="admin-card">
        <h2>{t('admin.audioCompute.workers')}</h2>
        <div className="admin-toolbar">
          <input
            type="text"
            placeholder="worker name"
            value={newName}
            onChange={(e) =>
              setNewName(e.target.value)
            }
            maxLength={64}
          />
          <select
            value={newProfile}
            onChange={(e) =>
              setNewProfile(e.target.value)
            }
          >
            <option value="cpu_light">
              cpu_light
            </option>
            <option value="gpu_full">
              gpu_full
            </option>
          </select>
          <Press
            variant="ghost"
            disabled={
              !newName ||
              createWorker.isPending
            }
            onClick={() =>
              createWorker.mutate({
                name: newName,
                profile: newProfile,
              })
            }
          >
            Create worker
          </Press>
        </div>
        {showSecret && (
          <div className="admin-card admin-card--inline">
            <p>
              Save this secret — it will not be
              shown again:
            </p>
            <code className="admin-mono">
              {showSecret}
            </code>
            <Press
              variant="ghost"
              onClick={() => setShowSecret(null)}
            >
              Dismiss
            </Press>
          </div>
        )}
        <DataTable
          columns={[
            ...workerColumns,
            {
              header: '',
              id: 'actions',
              cell: (i) => (
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                  }}
                >
                  <Press
                    variant="ghost"
                    onClick={() =>
                      rotateSecret.mutate(
                        i.row.original.id,
                      )
                    }
                  >
                    Rotate
                  </Press>
                  <Press
                    variant="ghost"
                    onClick={() =>
                      revokeWorker.mutate(
                        i.row.original.id,
                      )
                    }
                  >
                    Revoke
                  </Press>
                </div>
              ),
            },
          ]}
          rows={
            (workers.data as
              | WorkerRow[]
              | undefined) || []
          }
          emptyHint="No workers registered"
        />
      </section>

      <section className="admin-card">
        <h2>{t('admin.audioCompute.jobs')}</h2>
        <DataTable
          columns={jobColumns}
          rows={
            (jobs.data as
              | JobRow[]
              | undefined) || []
          }
          emptyHint="No jobs in flight"
        />
      </section>

      <section className="admin-card">
        <h2>Worker audit (last 200)</h2>
        <DataTable
          columns={auditColumns}
          rows={
            (audit.data as
              | AuditRow[]
              | undefined) || []
          }
        />
      </section>
    </div>
  )
}
